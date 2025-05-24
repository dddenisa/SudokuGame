import asyncio
import pygame
import random
import time
import webbrowser
import os
import http.server
import socketserver
import threading
import sys
import json
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

pygame.init()
pygame.mixer.init()
try:
    error_sound = pygame.mixer.Sound("error.wav")
    success_sound = pygame.mixer.Sound("success.wav")
except:
    error_sound = None
    success_sound = None
try:
    logo_img = pygame.image.load("Background.png")
except:
    logo_img = None

# Load Twilio configuration (replace with actual credentials or environment variables)
try:
    from config import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_NUMBER, PLAYER_WHATSAPP_NUMBER
except ImportError:
    TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID', '*****************************')
    TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN', '*******************************')
    TWILIO_WHATSAPP_NUMBER = os.getenv('TWILIO_WHATSAPP_NUMBER', 'whatsapp:+14155238886')
    PLAYER_WHATSAPP_NUMBER = os.getenv('PLAYER_WHATSAPP_NUMBER', 'whatsapp:+**********')

HEADER_HEIGHT = 60
WHITE = (255, 255, 255)
LINE_COLOR = (0, 0, 0)
SELECTED_COLOR = (200, 200, 255)
ERROR_COLOR = (255, 0, 0)
SUCCESS_COLOR = (0, 255, 0)
SELECTED_OPACITY = 128
FONT = pygame.font.Font(None, 40)
NOTE_FONT = pygame.font.Font(None, 25)
TITLE_FONT = pygame.font.Font(None, 80)

DIFFICULTIES = {
    "usor": 30,
    "mediu": 40,
    "greu": 55
}

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PAYMENT_SUCCESS_FILE = os.path.join(CURRENT_DIR, "payment_success.txt")
SERVER_RUNNING = threading.Event()
SERVER_RUNNING.set()

class PaymentRequestHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_POST(self):
        if self.path == '/confirm_payment':
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                print(f"Received POST data: {post_data.decode('utf-8')}")
                data = json.loads(post_data.decode('utf-8'))
                chances = data.get('chances')
                if chances in ['10', '25']:
                    with open(PAYMENT_SUCCESS_FILE, "w") as f:
                        f.write(str(chances))
                        f.flush()
                        os.fsync(f.fileno())
                    print(f"Successfully wrote to {PAYMENT_SUCCESS_FILE}")
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(b'{"status": "success"}')
                else:
                    print(f"Invalid chances value: {chances}")
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(b'{"error": "Invalid chances"}')
            except json.JSONDecodeError as e:
                print(f"JSON decode error: {e}")
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b'{"error": "Invalid JSON"}')
            except Exception as e:
                print(f"Server error: {e}")
                self.send_response(500)
                self.end_headers()
                self.wfile.write(f'{"error": "Server error: {e}"}'.encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

httpd = None

def start_server():
    global httpd
    Handler = PaymentRequestHandler
    os.chdir(CURRENT_DIR)
    httpd = socketserver.TCPServer(("", 8000), Handler)
    print("Serving payment page at http://localhost:8000 from directory:", os.getcwd())
    while SERVER_RUNNING.is_set():
        httpd.handle_request()
    httpd.server_close()
    print("HTTP server stopped")

server_thread = threading.Thread(target=start_server, daemon=True)
server_thread.start()

def generate_solved_grid(grid_size=9, box_size=3):
    def is_valid(grid, row, col, num):
        for i in range(grid_size):
            if grid[row][i] == num or grid[i][col] == num:
                return False
        start_row, start_col = box_size * (row // box_size), box_size * (col // box_size)
        for i in range(start_row, start_row + box_size):
            for j in range(start_col, start_col + box_size):
                if grid[i][j] == num:
                    return False
        return True

    def solve(grid):
        for row in range(grid_size):
            for col in range(grid_size):
                if grid[row][col] == 0:
                    nums = list(range(1, grid_size + 1))
                    random.shuffle(nums)
                    for num in nums:
                        if is_valid(grid, row, col, num):
                            grid[row][col] = num
                            if solve(grid):
                                return True
                            grid[row][col] = 0
                    return False
        return True

    grid = [[0 for _ in range(grid_size)] for _ in range(grid_size)]
    solve(grid)
    return grid

def create_puzzle(board, num_empty_cells=40):
    puzzle = [row[:] for row in board]
    count = 0
    while count < num_empty_cells:
        row = random.randint(0, len(board) - 1)
        col = random.randint(0, len(board) - 1)
        if puzzle[row][col] != 0:
            puzzle[row][col] = 0
            count += 1
    return puzzle

def draw_grid(screen, grid_size, box_size, screen_width, screen_height):
    block_size = screen_width // grid_size
    for i in range(grid_size + 1):
        line_width = 4 if i % box_size == 0 else 1
        pygame.draw.line(screen, LINE_COLOR, (0, i * block_size + HEADER_HEIGHT), (screen_width, i * block_size + HEADER_HEIGHT), line_width)
        pygame.draw.line(screen, LINE_COLOR, (i * block_size, HEADER_HEIGHT), (i * block_size, HEADER_HEIGHT + screen_height), line_width)

def draw_numbers(screen, grid, grid_size, screen_width):
    block_size = screen_width // grid_size
    for row in range(grid_size):
        for col in range(grid_size):
            if grid[row][col] != 0:
                num_str = str(grid[row][col]) if grid[row][col] <= 9 else chr(ord('A') + grid[row][col] - 10)
                num_text = FONT.render(num_str, True, (0, 0, 0))
                x = col * block_size + block_size // 2 - num_text.get_width() // 2
                y = row * block_size + HEADER_HEIGHT + block_size // 2 - num_text.get_height() // 2
                screen.blit(num_text, (x, y))

def draw_notes(screen, notes, grid_size, screen_width):
    block_size = screen_width // grid_size
    note_font = pygame.font.Font(None, 20)
    for row in range(grid_size):
        for col in range(grid_size):
            if notes[row][col]:
                note_size = 4 if grid_size == 16 else 3
                for note in notes[row][col]:
                    note_str = str(note) if note <= 9 else chr(ord('A') + note - 10)
                    note_text = note_font.render(note_str, True, (100, 100, 100))
                    nx = col * block_size + ((note - 1) % note_size) * (block_size // note_size)
                    ny = row * block_size + HEADER_HEIGHT + ((note - 1) // note_size) * (block_size // note_size)
                    screen.blit(note_text, (nx + 5, ny + 5))

def draw_selected_cell(screen, selected, grid_size, error_cells, screen_width, error_flash=False, success_flash=False):
    if selected:
        block_size = screen_width // grid_size
        row, col = selected
        if error_flash:
            color = ERROR_COLOR
            opacity = 200
        elif success_flash:
            color = SUCCESS_COLOR
            opacity = 200
        else:
            color = ERROR_COLOR if error_cells[row][col] else SELECTED_COLOR
            opacity = SELECTED_OPACITY
        selection_surface = pygame.Surface((block_size, block_size), pygame.SRCALPHA)
        selection_surface.fill((*color, opacity))
        screen.blit(selection_surface, (col * block_size, row * block_size + HEADER_HEIGHT))

def draw_header(screen, elapsed_seconds, note_mode, max_mistakes, screen_width):
    pygame.draw.rect(screen, (230, 230, 230), (0, 0, screen_width, HEADER_HEIGHT))
    title_text = FONT.render("Sudoku", True, (0, 0, 0))
    screen.blit(title_text, (screen_width // 2 - title_text.get_width() // 2, 15))

    note_status = "ON" if note_mode else "OFF"
    note_text = NOTE_FONT.render(f"Notițe: {note_status}", True, (0, 255, 0) if note_status == "ON" else (25, 0, 0))
    screen.blit(note_text, (screen_width - 350, 40))

    minutes = elapsed_seconds // 60
    seconds = elapsed_seconds % 60
    time_text = FONT.render(f"{minutes:02}:{seconds:02}", True, (0, 0, 0))
    screen.blit(time_text, (screen_width - 100, 15))

    mistakes_text = NOTE_FONT.render(f"Greșeli rămase: {max_mistakes}", True, (0, 0, 0))
    screen.blit(mistakes_text, (screen_width - 160, 40))

    mouse_pos = pygame.mouse.get_pos()
    menu_rect = pygame.Rect(10, 10, 90, 40)
    menu_color = (220, 220, 255) if menu_rect.collidepoint(mouse_pos) else (180, 180, 180)
    pygame.draw.rect(screen, menu_color, menu_rect, border_radius=6)
    menu_text = FONT.render("Meniu", True, (0, 0, 0))
    screen.blit(menu_text, (15, 15))

    reset_rect = pygame.Rect(115, 10, 90, 40)
    reset_color = (220, 220, 255) if reset_rect.collidepoint(mouse_pos) else (180, 180, 180)
    pygame.draw.rect(screen, reset_color, reset_rect, border_radius=6)
    reset_text = FONT.render("Reset", True, (0, 0, 0))
    screen.blit(reset_text, (120, 15))

def is_valid_move(grid, row, col, num, box_size):
    for i in range(len(grid)):
        if i != col and grid[row][i] == num:
            return False
        if i != row and grid[i][col] == num:
            return False
    start_row, start_col = box_size * (row // box_size), box_size * (col // box_size)
    for i in range(start_row, start_row + box_size):
        for j in range(start_col, start_col + box_size):
            if (i != row or j != col) and grid[i][j] == num:
                return False
    return True

def check_sudoku(grid, grid_size):
    for i in range(grid_size):
        row = [grid[i][j] for j in range(grid_size) if grid[i][j] != 0]
        col = [grid[j][i] for j in range(grid_size) if grid[j][i] != 0]
        if len(row) != len(set(row)) or len(col) != len(set(col)):
            return False
    box_size = 4 if grid_size == 16 else 3
    for row in range(0, grid_size, box_size):
        for col in range(0, grid_size, box_size):
            subgrid = [grid[r][c] for r in range(row, row + box_size) for c in range(col, col + box_size) if grid[r][c] != 0]
            if len(subgrid) != len(set(subgrid)):
                return False
    return all(grid[r][c] != 0 for r in range(grid_size) for c in range(grid_size))

def draw_success_message(screen, screen_width, screen_height):
    success_text = FONT.render("Sudoku completat corect!", True, (0, 255, 0))
    screen.blit(success_text, (screen_width // 2 - success_text.get_width() // 2, HEADER_HEIGHT + screen_height // 2))

def show_menu(screen, screen_width, screen_height, max_mistakes):
    running = True
    current_max_mistakes = max_mistakes  # Initialize with the passed max_mistakes
    buttons = [
        ("Ușor", 120),
        ("Mediu", 200),
        ("Greu", 280),
        ("4x4", 360),
        ("Ieșire", 440)
    ]
    button_colors = {
        "Ușor": (100, 200, 100),
        "Mediu": (240, 200, 100),
        "Greu": (220, 80, 80),
        "4x4": (200, 40, 40),
        "Ieșire": (150, 150, 150)
    }
    hover_color = (220, 220, 255)

    while running:
        screen.fill(WHITE)
        if logo_img:
            screen.blit(logo_img, (screen_width // 2 - logo_img.get_width() // 2, 20))
        title = TITLE_FONT.render("Sudoku!", True, (0, 0, 0))
        screen.blit(title, (screen_width // 2 - title.get_width() // 2, 25))

        mouse_pos = pygame.mouse.get_pos()
        for text, y in buttons:
            button_rect = pygame.Rect(200, y, 200, 50)
            color = hover_color if button_rect.collidepoint(mouse_pos) else button_colors.get(text, (180, 180, 180))
            pygame.draw.rect(screen, color, button_rect, border_radius=8)
            label = FONT.render(text, True, (0, 0, 0))
            screen.blit(label, (screen_width // 2 - label.get_width() // 2, y + 10))

        selector_y = 540
        minus_rect = pygame.Rect(148, selector_y, 30, 30)
        plus_rect = pygame.Rect(424, selector_y, 30, 30)
        mistakes_text = FONT.render(f"Greșeli permise: {current_max_mistakes}", True, (0, 0, 0))
        screen.blit(mistakes_text, (screen_width // 2 - mistakes_text.get_width() // 2, selector_y))

        pygame.draw.rect(screen, hover_color if minus_rect.collidepoint(mouse_pos) else (200, 200, 200), minus_rect, border_radius=6)
        minus = FONT.render("-", True, (0, 0, 0))
        screen.blit(minus, (158, selector_y))

        pygame.draw.rect(screen, hover_color if plus_rect.collidepoint(mouse_pos) else (200, 200, 200), plus_rect, border_radius=6)
        plus = FONT.render("+", True, (0, 0, 0))
        screen.blit(plus, (430, selector_y))

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return None, current_max_mistakes
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                x, y = event.pos
                for text, btn_y in buttons:
                    button_rect = pygame.Rect(200, btn_y, 200, 50)
                    if button_rect.collidepoint(x, y):
                        if text == "Ieșire":
                            return None, current_max_mistakes
                        return text.lower(), current_max_mistakes
                if minus_rect.collidepoint(x, y) and current_max_mistakes > 0:
                    current_max_mistakes -= 1
                elif plus_rect.collidepoint(x, y) and current_max_mistakes < 99:
                    current_max_mistakes += 1

        pygame.display.flip()

async def check_payment_confirmation(chances, screen, screen_width, screen_height, grid, grid_size, box_size, elapsed_seconds, note_mode, max_mistakes, selected, error_cells, notes, error_flash, success_flash):
    print(f"Checking for payment confirmation for {chances} chances...")
    start_time = time.time()
    timeout = 60
    initial_wait = True
    max_retries = 5
    retry_delay = 2

    while time.time() - start_time < timeout:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                print("Quit event detected during payment confirmation")
                return False, 0

        screen.fill(WHITE)
        draw_header(screen, elapsed_seconds, note_mode, max_mistakes, screen_width)
        draw_grid(screen, grid_size, box_size, screen_width, screen_height - HEADER_HEIGHT)
        draw_numbers(screen, grid, grid_size, screen_width)
        draw_notes(screen, notes, grid_size, screen_width)
        draw_selected_cell(screen, selected, grid_size, error_cells, screen_width, error_flash, success_flash)
        overlay = pygame.Surface((screen_width, screen_height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        screen.blit(overlay, (0, 0))
        pygame.draw.rect(screen, (255, 255, 255), (100, 180, 400, 330), border_radius=10)
        pygame.draw.rect(screen, (0, 0, 0), (100, 180, 400, 330), 2, border_radius=10)
        processing_text = FONT.render("Procesare plată...", True, (0, 0, 255))
        screen.blit(processing_text, (screen_width // 2 - processing_text.get_width() // 2, screen_height // 2 - 20))
        pygame.display.flip()

        if initial_wait:
            print("Waiting for initial delay to allow file creation...")
            await asyncio.sleep(3)
            initial_wait = False

        retry_count = 0
        while retry_count < max_retries:
            try:
                if os.path.exists(PAYMENT_SUCCESS_FILE):
                    with open(PAYMENT_SUCCESS_FILE, "r") as f:
                        content = f.read().strip()
                    print(f"Found file with content: {content} at {time.time() - start_time:.2f} seconds")
                    if content == str(chances):
                        try:
                            os.remove(PAYMENT_SUCCESS_FILE)
                            print(f"Payment confirmed for {chances} chances, removed {PAYMENT_SUCCESS_FILE}")
                            return True, int(chances)
                        except PermissionError as e:
                            print(f"Failed to remove file: {e}")
                            await asyncio.sleep(retry_delay)
                            retry_count += 1
                            continue
                break
            except PermissionError as e:
                print(f"Permission error accessing file: {e} at {time.time() - start_time:.2f} seconds, retry {retry_count + 1}/{max_retries}")
                await asyncio.sleep(retry_delay)
                retry_count += 1
            except Exception as e:
                print(f"Error checking payment file: {e} at {time.time() - start_time:.2f} seconds")
                break

        await asyncio.sleep(0.1)

    print(f"Payment confirmation timed out after {timeout} seconds")
    return False, 0

async def main():
    global httpd, SERVER_RUNNING
    SCREEN_WIDTH, SCREEN_HEIGHT = 600, 660
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption('Sudoku')
    FPS = 60
    clock = pygame.time.Clock()

    try:
        twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    except Exception as e:
        print(f"Failed to initialize Twilio client: {e}")
        twilio_client = None

    grid = None
    original_cells = None
    error_cells = None
    notes = None
    note_mode = False
    error_flash = False
    success_flash = False
    flash_start = 0
    max_mistakes = 3  # Initial value, represents remaining chances
    payment_failed = False
    last_interaction_time = time.time()
    message_sent = False

    def setup():
        nonlocal grid, original_cells, error_cells, notes, note_mode, error_flash, success_flash, flash_start, payment_failed, last_interaction_time, message_sent
        grid = None
        original_cells = None
        error_cells = None
        notes = None
        note_mode = False
        error_flash = False
        success_flash = False
        flash_start = 0
        payment_failed = False
        last_interaction_time = time.time()
        message_sent = False

    async def send_whatsapp_message():
        nonlocal message_sent
        if twilio_client and not message_sent:
            try:
                message = twilio_client.messages.create(
                    body="Hei, a trecut ceva timp de când ai jucat ultima dată sudoku. Intoarce-te și rezolvă puzzle-ul!",
                    from_=TWILIO_WHATSAPP_NUMBER,
                    to=PLAYER_WHATSAPP_NUMBER
                )
                print(f"WhatsApp message sent: SID {message.sid}")
                message_sent = True
                return True
            except TwilioRestException as e:
                print(f"Failed to send WhatsApp message: {e}")
                return False
        return False

    async def update_loop():
        nonlocal grid, original_cells, error_cells, notes, note_mode, error_flash, success_flash, flash_start, max_mistakes, payment_failed, last_interaction_time, message_sent
        while True:
            dificultate, max_mistakes = show_menu(screen, SCREEN_WIDTH, SCREEN_HEIGHT, max_mistakes)
            if not dificultate:
                break

            if dificultate == "4x4":
                grid_size = 16
                box_size = 4
                num_empty = 150
            else:
                grid_size = 9
                box_size = 3
                num_empty = DIFFICULTIES.get(dificultate, 40)

            solved_grid = generate_solved_grid(grid_size, box_size)
            grid = create_puzzle(solved_grid, num_empty_cells=num_empty)
            original_cells = [[cell != 0 for cell in row] for row in grid]
            error_cells = [[False for _ in range(grid_size)] for _ in range(grid_size)]
            notes = [[set() for _ in range(grid_size)] for _ in range(grid_size)]
            note_mode = False
            selected = None
            start_time = time.time()
            timer_stopped = False
            game_over = False
            error_flash = False
            success_flash = False
            flash_start = 0
            return_to_menu = False
            payment_failed = False
            last_interaction_time = time.time()
            message_sent = False

            while True:
                elapsed_seconds = int(time.time() - start_time) if not timer_stopped else elapsed_seconds
                screen.fill(WHITE)
                draw_header(screen, elapsed_seconds, note_mode, max_mistakes, SCREEN_WIDTH)
                draw_grid(screen, grid_size, box_size, SCREEN_WIDTH, SCREEN_HEIGHT - HEADER_HEIGHT)
                draw_numbers(screen, grid, grid_size, SCREEN_WIDTH)
                draw_notes(screen, notes, grid_size, SCREEN_WIDTH)
                draw_selected_cell(screen, selected, grid_size, error_cells, SCREEN_WIDTH, error_flash, success_flash)

                if not timer_stopped and time.time() - last_interaction_time >= 3600:
                    print("Inactivity detected for 30 seconds, sending WhatsApp message")
                    await send_whatsapp_message()

                if game_over:
                    overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
                    overlay.fill((0, 0, 0, 180))
                    screen.blit(overlay, (0, 0))
                    pygame.draw.rect(screen, (255, 255, 255), (100, 180, 400, 330), border_radius=10)
                    pygame.draw.rect(screen, (0, 0, 0), (100, 180, 400, 330), 2, border_radius=10)
                    message = FONT.render("Ai făcut prea multe greșeli!", True, (200, 0, 0))
                    screen.blit(message, (SCREEN_WIDTH // 2 - message.get_width() // 2, 210))
                    if payment_failed:
                        failed_text = FONT.render("Plata a eșuat. Încearcă din nou.", True, (255, 0, 0))
                        screen.blit(failed_text, (SCREEN_WIDTH // 2 - failed_text.get_width() // 2, 250))
                    pygame.draw.rect(screen, (180, 180, 180), (180, 300, 240, 50), border_radius=8)
                    back_text = FONT.render("Meniu Principal", True, (0, 0, 0))
                    screen.blit(back_text, (SCREEN_WIDTH // 2 - back_text.get_width() // 2, 310))
                    buy_10_rect = pygame.Rect(120, 370, 360, 50)
                    buy_10_color = (100, 200, 100) if buy_10_rect.collidepoint(pygame.mouse.get_pos()) else (80, 180, 80)
                    pygame.draw.rect(screen, buy_10_color, buy_10_rect, border_radius=8)
                    buy_10_text = FONT.render("Cumpără 10 Șanse (1 leu)", True, (0, 0, 0))
                    screen.blit(buy_10_text, (SCREEN_WIDTH // 2 - buy_10_text.get_width() // 2, 380))
                    buy_25_rect = pygame.Rect(120, 440, 360, 50)
                    buy_25_color = (100, 200, 100) if buy_25_rect.collidepoint(pygame.mouse.get_pos()) else (80, 180, 80)
                    pygame.draw.rect(screen, buy_25_color, buy_25_rect, border_radius=8)
                    buy_25_text = FONT.render("Cumpără 25 Șanse (2 lei)", True, (0, 0, 0))
                    screen.blit(buy_25_text, (SCREEN_WIDTH // 2 - buy_25_text.get_width() // 2, 450))

                if check_sudoku(grid, grid_size) and not timer_stopped:
                    if success_sound:
                        success_sound.play()
                    success_flash = True
                    flash_start = time.time()
                    draw_success_message(screen, SCREEN_WIDTH, SCREEN_HEIGHT - HEADER_HEIGHT)
                    timer_stopped = True

                if (error_flash or success_flash) and time.time() - flash_start > 0.5:
                    error_flash = False
                    success_flash = False

                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        print("Quit event detected in main loop")
                        SERVER_RUNNING.clear()
                        return
                    if event.type in (pygame.MOUSEBUTTONDOWN, pygame.KEYDOWN):
                        last_interaction_time = time.time()
                        message_sent = False
                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        mouse_x, mouse_y = pygame.mouse.get_pos()
                        if mouse_y > HEADER_HEIGHT and not game_over:
                            row = (mouse_y - HEADER_HEIGHT) // ((SCREEN_HEIGHT - HEADER_HEIGHT) // grid_size)
                            col = mouse_x // (SCREEN_WIDTH // grid_size)
                            if 0 <= row < grid_size and 0 <= col < grid_size:
                                selected = (row, col)
                        if pygame.Rect(10, 10, 90, 40).collidepoint(mouse_x, mouse_y):
                            return_to_menu = True
                            break
                        if pygame.Rect(115, 10, 90, 40).collidepoint(mouse_x, mouse_y):
                            solved_grid = generate_solved_grid(grid_size, box_size)
                            grid = create_puzzle(solved_grid, num_empty_cells=num_empty)
                            original_cells = [[cell != 0 for cell in row] for row in grid]
                            error_cells = [[False for _ in range(grid_size)] for _ in range(grid_size)]
                            notes = [[set() for _ in range(grid_size)] for _ in range(grid_size)]
                            start_time = time.time()
                            selected = None
                            game_over = False
                            timer_stopped = False
                            payment_failed = False
                            last_interaction_time = time.time()
                            message_sent = False
                        if game_over:
                            if pygame.Rect(180, 300, 240, 50).collidepoint(mouse_x, mouse_y):
                                return_to_menu = True
                                break
                            if buy_10_rect.collidepoint(mouse_x, mouse_y):
                                print("Opening payment page for 10 chances")
                                webbrowser.open("http://localhost:8000/payment.html?chances=10")
                                success, additional_chances = await check_payment_confirmation(10, screen, SCREEN_WIDTH, SCREEN_HEIGHT, grid, grid_size, box_size, elapsed_seconds, note_mode, max_mistakes, selected, error_cells, notes, error_flash, success_flash)
                                if success:
                                    print(f"Adding {additional_chances} chances, previous max_mistakes: {max_mistakes}")
                                    max_mistakes += additional_chances
                                    print(f"New max_mistakes: {max_mistakes}")
                                    game_over = False
                                    timer_stopped = False
                                    payment_failed = False
                                    if success_sound:
                                        success_sound.play()
                                else:
                                    print("Payment confirmation failed, staying in game-over state")
                                    payment_failed = True
                                last_interaction_time = time.time()
                                message_sent = False
                                continue
                            if buy_25_rect.collidepoint(mouse_x, mouse_y):
                                print("Opening payment page for 25 chances")
                                webbrowser.open("http://localhost:8000/payment.html?chances=25")
                                success, additional_chances = await check_payment_confirmation(25, screen, SCREEN_WIDTH, SCREEN_HEIGHT, grid, grid_size, box_size, elapsed_seconds, note_mode, max_mistakes, selected, error_cells, notes, error_flash, success_flash)
                                if success:
                                    print(f"Adding {additional_chances} chances, previous max_mistakes: {max_mistakes}")
                                    max_mistakes += additional_chances
                                    print(f"New max_mistakes: {max_mistakes}")
                                    game_over = False
                                    timer_stopped = False
                                    payment_failed = False
                                    if success_sound:
                                        success_sound.play()
                                else:
                                    print("Payment confirmation failed, staying in game-over state")
                                    payment_failed = True
                                last_interaction_time = time.time()
                                message_sent = False
                                continue
                    if event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_n:
                            note_mode = not note_mode
                        if selected and not game_over:
                            row, col = selected
                            number = None
                            if event.key in range(pygame.K_1, pygame.K_9 + 1):
                                number = event.key - pygame.K_0
                            elif grid_size == 16 and event.key in [pygame.K_a, pygame.K_b, pygame.K_c, pygame.K_d, pygame.K_e, pygame.K_f, pygame.K_g]:
                                number = 10 + (event.key - pygame.K_a)
                            if number and 1 <= number <= grid_size and not original_cells[row][col]:
                                if note_mode:
                                    if number in notes[row][col]:
                                        notes[row][col].remove(number)
                                    else:
                                        notes[row][col].add(number)
                                else:
                                    grid[row][col] = number
                                    notes[row][col].clear()
                                    if is_valid_move(grid, row, col, number, box_size):
                                        error_cells[row][col] = False
                                    else:
                                        error_cells[row][col] = True
                                        if error_sound:
                                            error_sound.play()
                                        error_flash = True
                                        flash_start = time.time()
                                        max_mistakes -= 1
                                        print(f"Mistake made, max_mistakes reduced to: {max_mistakes}")
                                        if max_mistakes <= 0:
                                            game_over = True
                                            timer_stopped = True
                        if event.key == pygame.K_BACKSPACE and selected:
                            row, col = selected
                            if not original_cells[row][col]:
                                grid[row][col] = 0
                                notes[row][col].clear()
                                error_cells[row][col] = False
                    if game_over and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        x, y = pygame.mouse.get_pos()
                        if pygame.Rect(180, 300, 240, 50).collidepoint(x, y):
                            return_to_menu = True
                            break

                if return_to_menu:
                    break

                pygame.display.flip()
                clock.tick(FPS)
                await asyncio.sleep(1.0 / FPS)

    setup()
    try:
        await update_loop()
    except Exception as e:
        print(f"Unhandled exception in main loop: {e}")
    finally:
        SERVER_RUNNING.clear()
        if httpd:
            httpd.server_close()
            print("HTTP server closed")

if __name__ == "__main__":
    if os.path.exists(PAYMENT_SUCCESS_FILE):
        try:
            os.remove(PAYMENT_SUCCESS_FILE)
        except Exception as e:
            print(f"Failed to clean up {PAYMENT_SUCCESS_FILE}: {e}")
    asyncio.run(main())