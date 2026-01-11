import pygame
import sys
import copy
import os
import random
import time
#===========================================================================INTIALIZING PYGAME===========================================================================
pygame.init()
#===========================================================================CONSTANTS===========================================================================
board_width = 640
panel_width = 250
width = board_width + panel_width  # Total: 890px
height = 640
square_size = board_width // 8
#===========================================================================COLORS===========================================================================
Panel_bg = (45, 45, 45)
Panel_border = (80, 80, 80)
Panel_text = (220, 220, 220)
Eval_white = (240, 240, 240)
Eval_black = (60, 60, 60)
Graph_line = (100, 200, 255)  # Blue line for graph
Grid_line = (70, 70, 70)
Light_square = (240 , 217 , 181)
Dark_square = (181 , 136 , 99)
White = (255 , 255 , 255)
Black = (0 , 0 , 0)
Highlight_color = (186 , 202 , 68)
Valid_move_color = (100 , 100 , 200)
Capture_move_color = (200 , 100 , 100)
Check_color = (255 , 100 , 100)
#===========================================================================BOARD===========================================================================
board = [
    ['r', 'n', 'b', 'q', 'k', 'b', 'n', 'r'],  # BLACK BACK RANK
    ['p', 'p', 'p', 'p', 'p', 'p', 'p', 'p'],  # BLACK PAWN RANK
    ['.', '.', '.', '.', '.', '.', '.', '.'],  
    ['.', '.', '.', '.', '.', '.', '.', '.'],  
    ['.', '.', '.', '.', '.', '.', '.', '.'],  
    ['.', '.', '.', '.', '.', '.', '.', '.'],  
    ['P', 'P', 'P', 'P', 'P', 'P', 'P', 'P'],  # WHITE PAWN RANK
    ['R', 'N', 'B', 'Q', 'K', 'B', 'N', 'R']   # WHITE BACK RANK
]
#===========================================================================PIECES===========================================================================
piece_symbols = {
    # White Pieces
    'K': '♔',  
    'Q': '♕',  
    'R': '♖',  
    'B': '♗',  
    'N': '♘',  
    'P': '♙',  
    
    # Black Pieces 
    'k': '♚',  
    'q': '♛',  
    'r': '♜',  
    'b': '♝',  
    'n': '♞',  
    'p': '♟'   
}
piece_images = {}
piece_moved = {
    'white_king' : False,
    'white_rook_a' : False,
    'white_rook_h' : False,
    'black_king' : False,
    'black_rook_a' : False,
    'black_rook_h' : False,
}
captured_pieces = {'white': [], 'black': []}
en_passant_target = None
promotion_pending = None
#===========================================================================FILES===========================================================================
Files = ['a' , 'b' , 'c' , 'd' , 'e' , 'f' , 'g' , 'h']
#===========================================================================WINDOW SETUP===========================================================================
screen = pygame.display.set_mode((width , height))
pygame.display.set_caption("CHESS GAME")
font = pygame.font.Font(None , 60)
small_font = pygame.font.Font(None , 30)
large_font = pygame.font.Font(None , 80)
tiny_font = pygame.font.Font(None, 20)
#===========================================================================GAME STATE===========================================================================
selected_square = None
current_turn = 'white'
move_history = []
valid_moves = []
game_over = False
game_result = ""
animating_move = None
animation_duration = 0.5
evaluation_history = []  
current_evaluation = 0 
transposition_table = {}
"""===========================================================================DRAW BORAD==========================================================================="""
def draw_board():
    for row in range(8):
        for col in range(8):
            x = col * square_size
            y = row * square_size
            if (row + col) % 2 == 0:
                color = Light_square
            else:
                color = Dark_square
            
            if selected_square and selected_square == (row , col):
                color = Highlight_color
            if (row , col) in valid_moves:
                target = board[row][col]
                if target != '.':
                    color = Capture_move_color
                else:
                    color = Valid_move_color
            
            piece = board[row][col]
            if piece.upper() == 'K':
                piece_color = 'white' if piece.isupper() else 'black'
                if is_in_check(piece_color):
                    color = Check_color

            pygame.draw.rect(screen , color , (x , y , square_size , square_size))

            if (row , col) in valid_moves:
                center_x = x + square_size // 2
                center_y = y + square_size // 2
                target = board[row][col]
                if target == '.':
                    pygame.draw.circle(screen, (100, 100, 100), (center_x, center_y), 12)
                else:
                    pygame.draw.circle(screen, (100, 100, 100), (center_x, center_y), 35, 5)
"""===========================================================================LOAD PIECES==========================================================================="""
def load_images():
    global piece_images
    pieces = ['king', 'queen', 'rook', 'bishop', 'knight', 'pawn']
    colors = ['white', 'black']

    for color in colors:
        for piece in pieces:
            filename = f"{color}_{piece}.png"
            path = os.path.join("assets", "pieces", filename)
            try:
                image = pygame.image.load(path)
                image = pygame.transform.smoothscale(image , (square_size , square_size))
                if color == 'white':
                    key = piece[0].upper()
                else:
                    key = piece[0].lower()
                if piece == 'knight':
                    key = 'N' if color == 'white' else 'n'
                piece_images[key] = image
            except pygame.error as e:
                print(f"Couldn't load {filename}: {e}")
                piece_images = None
                return False
    return True
"""===========================================================================DRAW PIECES==========================================================================="""
def draw_pieces():
    for row in range(8):
        for col in range(8):
            piece = board[row][col]
            
            if piece == '.':
                continue
            
            # Skip piece being animated
            if animating_move:
                from_square, _, _, anim_piece = animating_move
                if from_square == (row, col):
                    continue
            
            # Draw piece at its board position
            center_x = col * square_size + square_size// 2
            center_y = row * square_size + square_size // 2
            
            if images_loaded and piece in piece_images:
                image = piece_images[piece]
                rect = image.get_rect(center=(center_x, center_y))
                screen.blit(image, rect)
            else:
                symbol = piece_symbols[piece]
                text_color = White if piece.isupper() else Black
                text_surface = font.render(symbol, True, text_color)
                text_rect = text_surface.get_rect(center=(center_x, center_y))
                screen.blit(text_surface, text_rect)
    
    # Draw animated piece
    if animating_move:
        from_square, to_square, start_time, piece = animating_move
        from_row, from_col = from_square
        to_row, to_col = to_square
        
        # Calculate current position
        elapsed = (pygame.time.get_ticks() - start_time) / 1000.0
        progress = ease_in_out(min(elapsed / animation_duration, 1.0))
        
        from_x = from_col * square_size + square_size // 2
        from_y = from_row * square_size + square_size // 2
        to_x = to_col * square_size + square_size// 2
        to_y = to_row * square_size+ square_size // 2
        
        current_x = from_x + (to_x - from_x) * progress
        current_y = from_y + (to_y - from_y) * progress
        
        if images_loaded and piece in piece_images:
            image = piece_images[piece]
            rect = image.get_rect(center=(current_x, current_y))
            screen.blit(image, rect)
        else:
            symbol = piece_symbols[piece]
            text_color = White if piece.isupper() else Black
            text_surface = font.render(symbol, True, text_color)
            text_rect = text_surface.get_rect(center=(current_x, current_y))
            screen.blit(text_surface, text_rect)
"""===========================================================================DRAW INFO==========================================================================="""
def draw_info():
    info_surface = pygame.Surface((width, 40))
    info_surface.set_alpha(200)  # Transparency (0-255)
    info_surface.fill((50, 50, 50))  # Dark gray
    screen.blit(info_surface, (0, 0))

    if game_over:
        turn_text = "Game Over"
    else:
        turn_text = f"Turn: {current_turn.capitalize()}"
        if is_in_check(current_turn):
            turn_text += " - CHECK!"

    text_surface = small_font.render(turn_text , True , White)
    screen.blit(text_surface , (10,10))

    if selected_square:
        row,col = selected_square
        piece = board[row][col]

        file_letter = Files[col]
        rank_number = 8 - row
        chess_notation = f"{file_letter}{rank_number}"

        if piece == '.':
            info_text = f"Selected: {chess_notation} (empty)"
        else:
            piece_name = get_piece_name(piece)
            colour = "White" if piece.isupper() else "Black"
            selected_text = f"Selected: {chess_notation} - {colour} {piece_name}"
            num_moves = len(valid_moves)
            selected_text += f" ({num_moves} valid moves)"

        selected_surface = small_font.render(selected_text , True , White)
        screen.blit(selected_surface , (370,10))
"""===========================================================================DRAW GAME OVER==========================================================================="""
def draw_game_over():
    if not game_over:
        return
    
    overlay = pygame.Surface((width, height))
    overlay.set_alpha(180)
    overlay.fill((0, 0, 0))
    screen.blit(overlay, (0, 0))

    result_surface = large_font.render(game_result, True, White)
    result_rect = result_surface.get_rect(center=(width // 2, height // 2 - 40))
    screen.blit(result_surface, result_rect)

    instruction = "Click anywhere to close"
    instr_surface = small_font.render(instruction, True, White)
    instr_rect = instr_surface.get_rect(center=(width // 2, height // 2 + 40))
    screen.blit(instr_surface, instr_rect)
"""===========================================================================DRAW PROMOTION==========================================================================="""
def draw_promotion_ui():
    if not promotion_pending:
        return
    
    # Overlay
    overlay = pygame.Surface((width, height))
    overlay.set_alpha(180)
    overlay.fill((0, 0, 0))
    screen.blit(overlay, (0, 0))
    
    # Title
    title = "Promote Pawn - Choose:"
    title_surface = font.render(title, True, White)
    title_rect = title_surface.get_rect(center=(width // 2, height // 2 - 100))
    screen.blit(title_surface, title_rect)
    
    # Buttons for Q, R, B, N
    row, col = promotion_pending
    is_white = board[row][col].isupper()
    pieces = ['Q', 'R', 'B', 'N']
    
    button_y = height // 2
    for i, p in enumerate(pieces):
        x = 50 + i * 140
        button_rect = pygame.Rect(x, button_y, 120, 120)
        pygame.draw.rect(screen, Light_square, button_rect)
        pygame.draw.rect(screen, Black, button_rect, 3)
        
        # Use piece image if available, otherwise fall back to symbol
        piece_key = p if is_white else p.lower()
        if images_loaded and piece_key in piece_images:
            image = piece_images[piece_key]
            image_rect = image.get_rect(center=button_rect.center)
            screen.blit(image, image_rect)
        else:
            symbol = piece_symbols[piece_key]
            text = large_font.render(symbol, True, White if is_white else Black)
            text_rect = text.get_rect(center=button_rect.center)
            screen.blit(text, text_rect)
"""===========================================================================DRAW CO-ORDINATES==========================================================================="""
def draw_coordinates():
    """Draw rank and file labels."""
    coord_font = pygame.font.Font(None, 24)
    
    # Files (a-h)
    for col in range(8):
        x = col * square_size + square_size - 10
        y = 8 * square_size + 50
        text = coord_font.render(Files[col], True, White)
        screen.blit(text, (x, y))
    
    # Ranks (8-1)
    for row in range(8):
        x = 5
        y = row * square_size + 45
        rank = str(8 - row)
        text = coord_font.render(rank, True, White)
        screen.blit(text, (x, y))
"""===========================================================================DRAW EVALUATION BAR==========================================================================="""
def draw_evaluation_bar():
    """Draw vertical evaluation bar showing advantage"""
    bar_x = board_width + 20
    bar_y = 50
    bar_width = 30
    bar_height = 200
    
    # Background (border)
    pygame.draw.rect(screen, Panel_border, (bar_x, bar_y, bar_width, bar_height), 2)
    
    # Calculate fill based on evaluation (-10 to +10 scale)
    # Clamp evaluation to reasonable range
    clamped_eval = max(-10, min(10, current_evaluation))
    
    # Convert to percentage (0 = black winning, 0.5 = equal, 1 = white winning)
    eval_percentage = (clamped_eval + 10) / 20  # Maps -10 to +10 into 0 to 1
    
    # Calculate heights
    white_height = int(bar_height * eval_percentage)
    black_height = bar_height - white_height
    
    # Draw white advantage (bottom to middle)
    if white_height > 0:
        white_rect = pygame.Rect(bar_x + 2, bar_y + black_height, bar_width - 4, white_height)
        pygame.draw.rect(screen, Eval_white, white_rect)
    
    # Draw black advantage (top to middle)
    if black_height > 0:
        black_rect = pygame.Rect(bar_x + 2, bar_y, bar_width - 4, black_height)
        pygame.draw.rect(screen, Eval_black, black_rect)
    
    # Draw center line (equality)
    center_y = bar_y + bar_height // 2
    pygame.draw.line(screen, White, (bar_x, center_y), (bar_x + bar_width, center_y), 1)
    
    # Draw numeric evaluation
    if current_evaluation > 0:
        eval_text = f"+{current_evaluation:.1f}"
        text_color = White
    elif current_evaluation < 0:
        eval_text = f"{current_evaluation:.1f}"
        text_color = White
    else:
        eval_text = "0.0"
        text_color = White
    
    eval_surface = small_font.render(eval_text, True, text_color)
    eval_rect = eval_surface.get_rect(center=(bar_x + bar_width // 2, bar_y + bar_height + 20))
    screen.blit(eval_surface, eval_rect)
"""===========================================================================DRAW EVALUATION GRAPH==========================================================================="""
def draw_evaluation_graph():
    """Draw line graph showing evaluation over time"""
    graph_x = board_width + 70
    graph_y = 50
    graph_width = 160
    graph_height = 120
    
    # Background
    graph_rect = pygame.Rect(graph_x, graph_y, graph_width, graph_height)
    pygame.draw.rect(screen, (30, 30, 30), graph_rect)
    pygame.draw.rect(screen, Panel_border, graph_rect, 1)
    
    # Title
    title_surface = tiny_font.render("Evaluation", True, Panel_text)
    screen.blit(title_surface, (graph_x + 5, graph_y - 20))
    
    # Draw center line (0.0 evaluation)
    center_y = graph_y + graph_height // 2
    pygame.draw.line(screen, Grid_line, (graph_x, center_y), (graph_x + graph_width, center_y), 1)
    
    # Draw grid lines
    for i in range(1, 4):
        grid_y = graph_y + (graph_height // 4) * i
        pygame.draw.line(screen, Grid_line, (graph_x, grid_y), (graph_x + graph_width, grid_y), 1)
    
    # Draw evaluation line
    if len(evaluation_history) > 1:
        # Show last 20 moves
        display_evals = evaluation_history[-20:]
        
        points = []
        for i, eval_val in enumerate(display_evals):
            # X position
            x = graph_x + int((i / max(1, len(display_evals) - 1)) * graph_width)
            
            # Y position (clamp eval to -5 to +5 for display)
            clamped = max(-5, min(5, eval_val))
            y_ratio = (clamped + 5) / 10  # Map -5 to +5 into 0 to 1
            y = graph_y + graph_height - int(y_ratio * graph_height)
            
            points.append((x, y))
        
        # Draw the line
        if len(points) > 1:
            pygame.draw.lines(screen, Graph_line, False, points, 2)
            
            # Draw dots at each point
            for point in points:
                pygame.draw.circle(screen, Graph_line, point, 3)
    
    # Labels
    plus_label = tiny_font.render("+5", True, Panel_text)
    screen.blit(plus_label, (graph_x + graph_width + 5, graph_y))
    
    zero_label = tiny_font.render("0", True, Panel_text)
    screen.blit(zero_label, (graph_x + graph_width + 5, center_y - 8))
    
    minus_label = tiny_font.render("-5", True, Panel_text)
    screen.blit(minus_label, (graph_x + graph_width + 5, graph_y + graph_height - 10))
"""===========================================================================DRAW MOVE HISTORY==========================================================================="""
def draw_move_history():
    """Draw scrollable move history"""
    hist_x = board_width + 20
    hist_y = 190
    hist_width = 210
    hist_height = 200
    
    # Background
    hist_rect = pygame.Rect(hist_x, hist_y, hist_width, hist_height)
    pygame.draw.rect(screen, (30, 30, 30), hist_rect)
    pygame.draw.rect(screen, Panel_border, hist_rect, 1)
    
    # Title
    title_surface = small_font.render("Moves", True, White)
    screen.blit(title_surface, (hist_x + 5, hist_y - 25))
    
    if not move_history:
        no_moves = tiny_font.render("No moves yet", True, Panel_text)
        screen.blit(no_moves, (hist_x + 10, hist_y + 10))
        return
    
    # Draw moves (show last 14 moves)
    y_offset = hist_y + 10
    move_height = 25
    
    # Calculate which moves to show (last 14)
    start_idx = max(0, len(move_history) - 28)  # 14 pairs = 28 moves
    
    for i in range(start_idx, len(move_history), 2):
        if y_offset > hist_y + hist_height - move_height:
            break
        
        move_num = (i // 2) + 1
        white_move = move_history[i]
        black_move = move_history[i + 1] if i + 1 < len(move_history) else ""
        
        # Highlight last move
        if i >= len(move_history) - 2:
            highlight_rect = pygame.Rect(hist_x + 5, y_offset - 2, hist_width - 10, move_height - 2)
            pygame.draw.rect(screen, (60, 60, 80), highlight_rect)
        
        # Move number
        num_surface = tiny_font.render(f"{move_num}.", True, Panel_text)
        screen.blit(num_surface, (hist_x + 10, y_offset))
        
        # White's move
        white_surface = tiny_font.render(white_move, True, White)
        screen.blit(white_surface, (hist_x + 40, y_offset))
        
        # Black's move
        if black_move:
            black_surface = tiny_font.render(black_move, True, (180, 180, 180))
            screen.blit(black_surface, (hist_x + 130, y_offset))
        
        y_offset += move_height
"""===========================================================================DRAW CAPTURED PIECES PANEL==========================================================================="""
def draw_captured_pieces_panel():
    """Draw captured pieces in panel"""
    cap_x = board_width + 20
    cap_y = 410
    cap_width = 210
    cap_height = 100
    
    # Background
    cap_rect = pygame.Rect(cap_x, cap_y, cap_width, cap_height)
    pygame.draw.rect(screen, (30, 30, 30), cap_rect)
    pygame.draw.rect(screen, Panel_border, cap_rect, 1)
    
    # Title
    title_surface = small_font.render("Captured", True, White)
    screen.blit(title_surface, (cap_x + 5, cap_y - 25))
    
    # White's captured pieces (pieces black captured)
    white_label = tiny_font.render("Black captured:", True, Panel_text)
    screen.blit(white_label, (cap_x + 10, cap_y + 10))
    
    x_offset = cap_x + 10
    y_offset = cap_y + 30
    for piece in captured_pieces['white']:
        if piece == '.':
            continue
        if images_loaded and piece in piece_images:
            small_img = pygame.transform.scale(piece_images[piece], (25, 25))
            screen.blit(small_img, (x_offset, y_offset))
        else:
            symbol = piece_symbols.get(piece, '')
            if symbol:
                text = tiny_font.render(symbol, True, White)
                screen.blit(text, (x_offset, y_offset))
        x_offset += 28
        if x_offset > cap_x + cap_width - 30:
            break
    
    # Black's captured pieces (pieces white captured)
    black_label = tiny_font.render("White captured:", True, Panel_text)
    screen.blit(black_label, (cap_x + 10, cap_y + 55))
    
    x_offset = cap_x + 10
    y_offset = cap_y + 75
    for piece in captured_pieces['black']:
        if piece == '.':
            continue
        if images_loaded and piece in piece_images:
            small_img = pygame.transform.scale(piece_images[piece], (25, 25))
            screen.blit(small_img, (x_offset, y_offset))
        else:
            symbol = piece_symbols.get(piece, '')
            if symbol:
                text = tiny_font.render(symbol, True, Black)
                screen.blit(text, (x_offset, y_offset))
        x_offset += 28
        if x_offset > cap_x + cap_width - 30:
            break
"""===========================================================================DRAW GAME INFO PANEL==========================================================================="""
def draw_game_info_panel():
    """Draw current game status"""
    info_x = board_width + 20
    info_y = 530
    info_width = 210
    
    # Turn indicator
    turn_text = f"Turn: {current_turn.capitalize()}"
    if is_in_check(current_turn):
        turn_text += " - CHECK!"
        turn_color = (255, 100, 100)
    else:
        turn_color = White
    
    turn_surface = small_font.render(turn_text, True, turn_color)
    screen.blit(turn_surface, (info_x, info_y))
    
    # Material count
    white_material = count_material('white')
    black_material = count_material('black')
    advantage = white_material - black_material
    
    if advantage > 0:
        mat_text = f"Material: White +{advantage}"
    elif advantage < 0:
        mat_text = f"Material: Black +{abs(advantage)}"
    else:
        mat_text = "Material: Equal"
    
    mat_surface = tiny_font.render(mat_text, True, Panel_text)
    screen.blit(mat_surface, (info_x, info_y + 35))
    
    # Move count
    move_count_text = f"Move: {len(move_history)}"
    move_surface = tiny_font.render(move_count_text, True, Panel_text)
    screen.blit(move_surface, (info_x, info_y + 60))
"""===========================================================================DRAW RIGHT PANEL==========================================================================="""
def draw_right_panel():
    """Draw complete right panel with all components"""
    # Panel background
    panel_rect = pygame.Rect(board_width, 0, panel_width, height)
    pygame.draw.rect(screen, Panel_bg, panel_rect)
    
    # Draw all components
    # draw_evaluation_bar()
    # draw_evaluation_graph()
    draw_move_history()
    draw_captured_pieces_panel()
    draw_game_info_panel()
"""===========================================================================COUNT MATERIAL==========================================================================="""
def count_material(color):
    """Count material value for a color."""
    values = {'P': 1, 'N': 3, 'B': 3, 'R': 5, 'Q': 9}
    total = 0
    
    for row in board:
        for piece in row:
            if piece == '.':
                continue
            piece_color = 'white' if piece.isupper() else 'black'
            if piece_color == color:
                total += values.get(piece.upper(), 0)
    
    return total
"""===========================================================================GET PIECE NAME==========================================================================="""
def get_piece_name(piece):
    
    names = {
        'K': 'King', 'Q': 'Queen', 'R': 'Rook',
        'B': 'Bishop', 'N': 'Knight', 'P': 'Pawn',
        'k': 'King', 'q': 'Queen', 'r': 'Rook',
        'b': 'Bishop', 'n': 'Knight', 'p': 'Pawn'
    }
    return names.get(piece, '')
"""===========================================================================GET SQUARE FROM MOUSE==========================================================================="""
def get_square_from_mouse(pos):

    x,y = pos
    col = x // square_size
    row = y // square_size

    if 0 <= row < 8 and 0 <= col < 8:
        return(row,col)
    return None
"""===========================================================================WHITE PIECE==========================================================================="""
def is_white_piece(piece):
    return piece.isupper() and piece != '.'
"""===========================================================================BLACK PIECE==========================================================================="""
def is_black_piece(piece):
    return piece.islower() and piece != '.'
"""===========================================================================CURRENT PLAYER PIECE==========================================================================="""
def is_current_player_piece(piece):
    if current_turn == 'white':
        return is_white_piece(piece)
    else:
        return is_black_piece(piece)
"""===========================================================================ENEMY PIECE==========================================================================="""
def is_enemy_piece(piece , player_color):
    if player_color == "white":
        return is_black_piece(piece)
    else:
        return is_white_piece(piece)
"""===========================================================================MOVE PIECE==========================================================================="""
def move_piece(from_square , to_square):
    global en_passant_target , promotion_pending

    from_row,from_col = from_square
    to_row,to_col = to_square
    start_animation(from_square , to_square)

    piece = board[from_row][from_col]
    captured_piece = board[to_row][to_col]  

    while update_animation():
        draw_board()
        draw_pieces()
        pygame.display.flip()
        clock.tick(60)
    
    if piece.upper() == 'K' and abs(to_col - from_col) == 2:
        execute_castling(from_row, from_col, to_col)
        update_pieces_moved(piece, from_row, from_col)
        return True
    
    is_en_passant = False
    if piece.upper() == 'P' and to_col != from_col and board[to_row][to_col] == '.':
        is_en_passant = True
        board[to_row][to_col] = piece
        board[from_row][from_col] = '.'
        board[from_row][to_col] = '.'  
    else:
        board[to_row][to_col] = piece
        board[from_row][from_col] = '.'
    
    update_pieces_moved(piece , from_row , from_col)

    en_passant_target = None
    if piece.upper() == 'P' and abs(to_row - from_row) == 2:
        ep_row = (from_row + to_row) // 2
        en_passant_target = (ep_row, to_col)
    
    if piece.upper() == 'P':
        if (piece == 'P' and to_row == 0) or (piece == 'p' and to_row == 7):
            promotion_pending = (to_row, to_col)

    from_notation = f"{Files[from_col]}{8 - from_row}"
    to_notation = f"{Files[to_col]}{8 - to_row}"
    if captured_piece != '.':
        if is_white_piece(captured_piece):
            captured_pieces['white'].append(captured_piece)
        move_str = f"{from_notation} x {to_notation}"
        print(f"Capture! {get_piece_name(piece)} takes {get_piece_name(captured_piece)}")
    else:
        captured_pieces['black'].append(captured_piece)
        move_str  = f"{from_notation} → {to_notation}"
    
    move_history.append(move_str)
    print(f"Move: {move_str}")
    current_evaluation = evaluate_board() / 100  # Convert to pawn units
    evaluation_history.append(current_evaluation)

    return True
"""===========================================================================PIECE IS ON BOARD==========================================================================="""
def is_on_board(row , col):
    return 0 <= row < 8 and 0 <= col < 8
"""===========================================================================FIND KING==========================================================================="""
def find_king(color):
    target_king = 'K' if color == 'white' else 'k'
    
    for row in range(8):
        for col in range(8):
            if board[row][col] == target_king:
                return (row, col)
    
    return None
"""===================================================================================================================================================================="""
#===========================================================================GET PIECE MOVES===========================================================================
def get_piece_moves(row , col):
    piece = board[row][col]
    if piece == '.':
        return[]
    piece_type = piece.upper()
    if piece_type == 'P':
        return get_pawn_moves(row , col , piece)
    elif piece_type == 'R':
        return get_rook_moves(row , col , piece)
    elif piece_type == 'N':
        return get_knight_moves(row , col , piece)
    elif piece_type == 'B':
        return get_bishop_moves(row , col , piece)
    elif piece_type == 'Q':
        return get_queen_moves(row , col , piece)
    elif piece_type == 'K':
        return get_king_moves(row , col , piece)
    return[]
#===========================================================================PAWN MOVES===========================================================================
def get_pawn_moves(row , col , piece):
    moves = []
    
    if piece.isupper():
        direction = -1
        start_row = 6 
        en_passant_row = 3 
    else:  
        direction = 1
        start_row = 1 
        en_passant_row = 4 
    
    new_row = row + direction
    if is_on_board(new_row, col):
        if board[new_row][col] == '.':
            moves.append((new_row, col))
            
            if row == start_row:
                new_row_2 = row + (2 * direction)
                if board[new_row_2][col] == '.':
                    moves.append((new_row_2, col))

    player_color = 'white' if piece.isupper() else 'black'
    for col_offset in [-1, 1]:  
        new_row = row + direction
        new_col = col + col_offset
        
        if is_on_board(new_row, new_col):
            target = board[new_row][new_col]
            if target != '.' and is_enemy_piece(target, player_color):
                moves.append((new_row, new_col))
    
    if row == en_passant_row and en_passant_target:
        ep_row , ep_col = en_passant_target
        if abs(ep_col - col) == 1 and ep_row == row + direction:
            moves.append((ep_row , ep_col))
    
    return moves
#===========================================================================ROOK MOVES===========================================================================
def get_rook_moves(row , col , piece):
    moves = []
    player_color = 'white' if piece.isupper() else 'black'
    directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    
    for d_row, d_col in directions:
        current_row = row + d_row
        current_col = col + d_col
        
        while is_on_board(current_row, current_col):
            target = board[current_row][current_col]
            
            if target == '.':
                moves.append((current_row, current_col))
            elif is_enemy_piece(target, player_color):
                moves.append((current_row, current_col))
                break 
            else:
                break
            
            current_row += d_row
            current_col += d_col
    
    return moves
#===========================================================================KNIGHT MOVES===========================================================================
def get_knight_moves(row , col , piece):
    moves = []
    player_color = 'white' if piece.isupper() else 'black'
    knight_moves = [
        (-2, -1), (-2, 1),   
        (-1, -2), (-1, 2),   
        (1, -2),  (1, 2),    
        (2, -1),  (2, 1)     
    ]
    
    for d_row, d_col in knight_moves:
        new_row = row + d_row
        new_col = col + d_col
        
        if is_on_board(new_row, new_col):
            target = board[new_row][new_col]
            
            if target == '.' or is_enemy_piece(target, player_color):
                moves.append((new_row, new_col))
    
    return moves
#===========================================================================BHISHOP MOVES===========================================================================
def get_bishop_moves(row , col , piece):
    moves = []
    player_color = 'white' if piece.isupper() else 'black'
    directions = [(-1, -1), (-1, 1), (1, -1), (1, 1)]
    
    for d_row, d_col in directions:
        current_row = row + d_row
        current_col = col + d_col
        
        while is_on_board(current_row, current_col):
            target = board[current_row][current_col]
            
            if target == '.':
                moves.append((current_row, current_col))
            elif is_enemy_piece(target, player_color):
                moves.append((current_row, current_col))
                break
            else:
                break
            
            current_row += d_row
            current_col += d_col
    
    return moves
#===========================================================================QUEEN MOVES===========================================================================
def get_queen_moves(row , col , piece):
    moves = []
    
    moves.extend(get_rook_moves(row, col, piece))
    moves.extend(get_bishop_moves(row, col, piece))
    
    return moves
#===========================================================================KING MOVES===========================================================================
def get_king_moves(row , col , piece, include_castling=True):
    moves = []
    player_color = 'white' if piece.isupper() else 'black'
    directions = [
        (-1, -1), (-1, 0), (-1, 1),
        (0, -1),           (0, 1),
        (1, -1),  (1, 0),  (1, 1)
    ]
    
    for d_row, d_col in directions:
        new_row = row + d_row
        new_col = col + d_col
        
        if is_on_board(new_row, new_col):
            target = board[new_row][new_col]
            
            if target == '.' or is_enemy_piece(target, player_color):
                moves.append((new_row, new_col))
    if include_castling:
        if can_castle_kingside(player_color):
            moves.append((row , 6))
        if can_castle_queenside(player_color):
            moves.append((row , 2))
    return moves
#===========================================================================CASTLE KINGSIDE===========================================================================
def can_castle_kingside(color):
    if color == 'white':
        king_row, king_col = 7, 4
        rook_col = 7
        if piece_moved['white_king'] or piece_moved['white_rook_h']:
            return False
    else:
        king_row, king_col = 0, 4
        rook_col = 7
        if piece_moved['black_king'] or piece_moved['black_rook_h']:
            return False
    
    for col in range(king_col + 1, rook_col):
        if board[king_row][col] != '.':
            return False
    
    if is_in_check(color):
        return False
    
    enemy_color = 'black' if color == 'white' else 'white'
    for col in [king_col + 1, king_col + 2]:
        if is_square_attacked(king_row, col, enemy_color):
            return False
    
    return True
#===========================================================================CASTLE QUEENSIDE===========================================================================
def can_castle_queenside(color):
    if color == 'white':
        king_row, king_col = 7, 4
        rook_col = 0
        if piece_moved['white_king'] or piece_moved['white_rook_a']:
            return False
    else:
        king_row, king_col = 0, 4
        rook_col = 0
        if piece_moved['black_king'] or piece_moved['black_rook_a']:
            return False
    
    for col in range(rook_col + 1, king_col):
        if board[king_row][col] != '.':
            return False
    
    if is_in_check(color):
        return False
    
    enemy_color = 'black' if color == 'white' else 'white'
    for col in [king_col - 1, king_col - 2]:
        if is_square_attacked(king_row, col, enemy_color):
            return False
    
    return True
#===========================================================================EXECUTE CASATLING===========================================================================
def execute_castling(king_row, king_col, target_col):
    if target_col == 6:  # Kingside
        board[king_row][6] = board[king_row][4]  # Move king
        board[king_row][5] = board[king_row][7]  # Move rook
        board[king_row][4] = '.'
        board[king_row][7] = '.'
    else:  # Queenside 
        board[king_row][2] = board[king_row][4]  # Move king
        board[king_row][3] = board[king_row][0]  # Move rook
        board[king_row][4] = '.'
        board[king_row][0] = '.'
#===========================================================================PROMOTE PAWN===========================================================================
def promote_pawn(row , col , piece_type):
    is_white = board[row][col].isupper()
    board[row][col] = piece_type.upper() if is_white else piece_type.lower()
"""===================================================================================================================================================================="""
"""===========================================================================UPDATE PIECES MOVED==========================================================================="""
def update_pieces_moved(piece , from_row , from_col):
    if piece == 'K':
        piece_moved['white_king'] = True
    elif piece == 'k':
        piece_moved['black_king'] = True
    elif piece == 'R':
        if from_row == 7 and from_col == 0:
            piece_moved['white_rook_a'] = True
        elif from_row == 7 and from_col == 7:
            piece_moved['white_rook_h'] = True
    elif piece == 'r':
        if from_row == 0 and from_col == 0:
            piece_moved['black_rook_a'] = True
        elif from_row == 0 and from_col == 7:
            piece_moved['black_rook_h'] = True
"""===========================================================================IS SQUARE ATTACKED==========================================================================="""
def is_square_attacked(row , col , by_color):
    for r in range(8):
        for c in range(8):
            piece = board[r][c]
            if piece == '.':
                continue

            piece_color = 'white' if piece.isupper() else 'black'
            if piece_color != by_color:
                continue

            # For kings, don't include castling moves when checking if square is attacked
            if piece.upper() == 'K':
                moves = get_king_moves(r, c, piece, include_castling=False)
            else:
                moves = get_piece_moves(r,c)
            if(row,col) in moves:
                return True
    return False
"""===========================================================================IS IN CHECK==========================================================================="""
def is_in_check(color):
    king_pos = find_king(color)
    if king_pos is None:
        return False
    row , col = king_pos
    enemy_color = 'black' if color == 'white' else 'white'
    return is_square_attacked(row , col , enemy_color)
"""===========================================================================WOULD BE CHECK AFTER MOVE==========================================================================="""
def would_be_in_check_after_move(from_square , to_square , color):
    global board
    original_board = copy.deepcopy(board)

    from_row, from_col = from_square
    to_row, to_col = to_square
    board[to_row][to_col] = board[from_row][from_col]
    board[from_row][from_col] = '.'
    in_check = is_in_check(color)
    board = original_board
    return in_check
"""===========================================================================GET VALID MOVES==========================================================================="""
def get_valid_moves(row , col):
    piece = board[row][col]
    if piece == '.':
        return []
    
    player_color = 'white' if piece.isupper() else 'black'
    
    # Get all possible moves
    possible_moves = get_piece_moves(row, col)
    # Filter out moves that would leave king in check
    legal_moves = []
    for move in possible_moves:
        # Simulate the move and check if king would be in check
        if not would_be_in_check_after_move((row, col), move, player_color):
            legal_moves.append(move)
    
    return legal_moves
"""===========================================================================GET ALL LEGAL MOVES==========================================================================="""
def get_all_legal_moves(color):
    all_moves = []
    
    for row in range(8):
        for col in range(8):
            piece = board[row][col]
            
            if piece == '.':
                continue
            
            piece_color = 'white' if piece.isupper() else 'black'
            if piece_color == color:
                moves = get_valid_moves(row, col)
                for move in moves:
                    all_moves.append(((row, col), move))
    
    return all_moves
"""===========================================================================CHECK GAME OVER==========================================================================="""
def check_game_over():  
    global game_over, game_result
    
    legal_moves = get_all_legal_moves(current_turn)
    
    if len(legal_moves) == 0:
        game_over = True
        
        if is_in_check(current_turn):
            # King in check + no moves = Checkmate
            winner = 'Black' if current_turn == 'white' else 'White'
            game_result = f"Checkmate! {winner} wins!"
            print("\n" + "=" * 60)
            print(game_result)
            print("=" * 60)
        else:
            # King not in check + no moves = Stalemate
            game_result = "Stalemate! It's a draw!"
            print("\n" + "=" * 60)
            print(game_result)
            print("=" * 60)
        
        return True
    
    return False
"""===========================================================================START ANIMATION==========================================================================="""
def start_animation(from_square , to_square):
    global animating_move
    from_row , from_col = from_square
    piece = board[from_row][from_col]
    animating_move = (from_square , to_square , pygame.time.get_ticks() , piece)
"""===========================================================================UPDATE ANIMATIONS==========================================================================="""
def update_animation():
    global animating_move
    
    if not animating_move:
        return False  
    
    from_square, to_square, start_time, piece = animating_move
    
    elapsed = (pygame.time.get_ticks() - start_time) / 1000.0
    progress = min(elapsed / animation_duration, 1.0)
    
    progress = ease_in_out(progress)
    
    if progress >= 1.0:
        animating_move = None
        return False
    
    return True
"""===========================================================================EASE IN OUT==========================================================================="""
def ease_in_out(t):
    if t < 0.5:
        return 4 * t * t * t
    else:
        return 1 - pow(-2 * t + 2, 3) / 2
"""===========================================================================SWITCH TURN==========================================================================="""
def switch_turn():
    global current_turn
    current_turn = 'black' if current_turn == 'white' else 'white'
    if is_in_check(current_turn):
        print(f"Check! {current_turn.capitalize()}'s king is under attack!")
    
    if not check_game_over():
        print(f"{current_turn.capitalize()}'s turn")
    
    print()
"""===========================================================================EVALUATE POSITION==========================================================================="""
def evaluate_position():
    score = 0
    piece_values = {'P': 1, 'N': 3, 'B': 3, 'R': 5, 'Q': 9, 'K': 0}
    
    for row in board:
        for piece in row:
            if piece in piece_values:
                score += piece_values[piece]  # White piece
            elif piece.lower() in piece_values:
                score -= piece_values[piece.lower()]  # Black piece
    
    return score
"""===========================================================================EVALUATE POSITION==========================================================================="""
def evaluate_board():
    """Evaluate current position. Positive = good for white."""
    score = 0
    piece_values = {'P': 1, 'N': 3, 'B': 3, 'R': 5, 'Q': 9}
    
    for row in board:
        for piece in row:
            if piece == '.':
                continue
            
            piece_type = piece.upper()
            if piece_type in piece_values:
                value = piece_values[piece_type]
                if piece.isupper():  # White
                    score += value
                else:  # Black
                    score -= value
    
    return score
"""===========================================================================SCORE MOVE==========================================================================="""
def score_move(from_square , to_square):
    from_row, from_col = from_square
    to_row, to_col = to_square
    
    piece = board[from_row][from_col]
    captured = board[to_row][to_col]
    
    score = 0

    if captured != '.':
        piece_values = {'P': 1, 'N': 3, 'B': 3, 'R': 5, 'Q': 9, 'K': 0}
        captured_value = piece_values.get(captured.upper(), 0)
        piece_value = piece_values.get(piece.upper(), 0)
        score = 10 * captured_value - piece_value

    if piece.upper() == 'P':
        if (piece == 'P' and to_row == 0) or (piece == 'p' and to_row == 7):
            score += 50
    if 2 <= to_row <= 5 and 2 <= to_col <= 5:
        score += 1
    return score
"""===========================================================================ORDERED MOVE==========================================================================="""
def get_ordered_move(color):
    moves = get_all_legal_moves(color)

    move_scores = []
    for from_sq, to_sq in moves:
        score = score_move(from_sq, to_sq)
        move_scores.append((score, from_sq, to_sq))
    move_scores.sort(reverse=True , key=lambda x: x[0])
    return [(from_sq, to_sq) for _, from_sq, to_sq in move_scores]
"""===========================================================================RANDOM MOVE AI==========================================================================="""
def get_random_move(color):
    """Get a random legal move for the given color."""
    all_moves = []
    
    # Get all pieces of this color
    for row in range(8):
        for col in range(8):
            piece = board[row][col]
            if piece == '.':
                continue
            
            piece_color = 'white' if piece.isupper() else 'black'
            if piece_color == color:
                moves = get_valid_moves(row, col)
                for move in moves:
                    all_moves.append(((row, col), move))
    
    if not all_moves:
        return None  # No legal moves (checkmate/stalemate)
    
    return random.choice(all_moves)
"""===========================================================================MATERIAL MOVE AI==========================================================================="""
def get_best_move_material(color):
    """Get move that results in best material balance."""
    global board
    all_moves = []
    
    # Get all legal moves with their resulting positions
    for r in range(8):
        for c in range(8):
            piece = board[r][c]
            if piece == '.':
                continue
            
            piece_color = 'white' if piece.isupper() else 'black'
            if piece_color == color:
                moves = get_valid_moves(r, c)
                for move in moves:
                    all_moves.append(((r, c), move))
    
    if not all_moves:
        return None
    
    best_move = None
    best_score = float('-inf') if color == 'white' else float('inf')
    
    for from_square, to_square in all_moves:
        # Simulate move
        original_board = copy.deepcopy(board)
        
        from_row, from_col = from_square
        to_row, to_col = to_square
        board[to_row][to_col] = board[from_row][from_col]
        board[from_row][from_col] = '.'
        
        # Evaluate
        score = evaluate_board()
        
        # Restore board
        board = copy.deepcopy(original_board)
        
        # Check if best
        if color == 'white':
            if score > best_score:
                best_score = score
                best_move = (from_square, to_square)
        else:
            if score < best_score:
                best_score = score
                best_move = (from_square, to_square)
    
    return best_move
"""===========================================================================POSITION HASH==========================================================================="""
def position_hash():
    """Create a unique hash for current board position."""
    return str(board) 
"""===========================================================================BEST MOVE ITERATIVE==========================================================================="""
def get_best_move_iterative(color, max_time=5.0):
    """
    Search with iterative deepening.
    
    max_time: Maximum seconds to think
    """
    best_move = None
    start_time = time.time()
    
    for depth in range(1, 10):  # Try depths 1 through 9
        if time.time() - start_time > max_time:
            break  # Out of time!
        
        try:
            move, score = minimax_root(color, depth)
            best_move = move
            print(f"Depth {depth}: score {score}, move {move}")
        
        except TimeoutError:
            break
    
    return best_move
"""===========================================================================MINIMAX ROOT==========================================================================="""
def minimax_root(color, depth):
    """Top-level minimax that returns best move."""
    global board
    moves = get_ordered_move(color)
    best_move = moves[0] if moves else None
    best_score = float('-inf') if color == 'white' else float('inf')
    
    alpha = float('-inf')
    beta = float('inf')
    
    for move in moves:
        from_sq, to_sq = move
        from_row, from_col = from_sq
        to_row, to_col = to_sq
        
        # Make move
        original_board = copy.deepcopy(board)
        board[to_row][to_col] = board[from_row][from_col]
        board[from_row][from_col] = '.'
        
        score = minimax(depth - 1, color == 'black', alpha, beta)
        
        # Undo move
        board = copy.deepcopy(original_board)
        
        if color == 'white':
            if score > best_score:
                best_score = score
                best_move = move
            alpha = max(alpha, score)
        else:
            if score < best_score:
                best_score = score
                best_move = move
            beta = min(beta, score)
        
        if beta <= alpha:
            break
    
    return best_move, best_score
"""===========================================================================MINIMAX==========================================================================="""
def minimax(depth, is_maximizing, alpha=float('-inf'), beta=float('inf')):
    """
    Minimax with alpha-beta pruning.
    
    depth: How many moves to look ahead
    is_maximizing: True if white's turn, False if black's
    alpha/beta: For pruning (explained in Lesson 9)
    """
    global board
    # Base case: reached max depth or game over
    pos_hash = position_hash()
    if pos_hash in transposition_table:
        stored_depth, stored_score = transposition_table[pos_hash]
        if stored_depth >= depth:
            return stored_score

    if depth == 0:
        final_score = evaluate_board()
        transposition_table[pos_hash] = (depth, final_score)
        return final_score
    
    legal_moves = get_ordered_move('white' if is_maximizing else 'black')
    
    if not legal_moves:
        # Checkmate or stalemate
        if is_in_check('white' if is_maximizing else 'black'):
            final_score = -10000 if is_maximizing else 10000  # Checkmate
        else:
            final_score = 0  # Stalemate
        transposition_table[pos_hash] = (depth, final_score)
        return final_score
    
    if is_maximizing:
        max_eval = float('-inf')
        for from_square, to_square in legal_moves:
            # Make move
            original_board = copy.deepcopy(board)
            from_row, from_col = from_square
            to_row, to_col = to_square
            board[to_row][to_col] = board[from_row][from_col]
            board[from_row][from_col] = '.'
            
            # Recurse
            eval = minimax(depth - 1, False, alpha, beta)
            
            # Undo move
            board = copy.deepcopy(original_board)
            
            max_eval = max(max_eval, eval)
            alpha = max(alpha, eval)
            if beta <= alpha:
                break  # Pruning
        
        transposition_table[pos_hash] = (depth, max_eval)
        return max_eval
    
    else:
        min_eval = float('inf')
        for from_square, to_square in legal_moves:
            # Make move
            original_board = copy.deepcopy(board)
            from_row, from_col = from_square
            to_row, to_col = to_square
            board[to_row][to_col] = board[from_row][from_col]
            board[from_row][from_col] = '.'
            
            # Recurse
            eval = minimax(depth - 1, True, alpha, beta)
            
            # Undo move
            board = copy.deepcopy(original_board)
            
            min_eval = min(min_eval, eval)
            beta = min(beta, eval)
            if beta <= alpha:
                break  # Pruning
        
        transposition_table[pos_hash] = (depth, min_eval)
        return min_eval
"""===========================================================================MINIMAX MOVE AI==========================================================================="""
def get_best_move_minimax(color, depth=3):
    """Get best move using minimax algorithm."""
    global board
    all_moves = []
    for row in range(8):
        for col in range(8):
            piece = board[row][col]
            if piece == '.':
                continue
            piece_color = 'white' if piece.isupper() else 'black'
            if piece_color == color:
                moves = get_valid_moves(row, col)
                for move in moves:
                    all_moves.append(((row, col), move))
    
    if not all_moves:
        return None
    
    best_move = None
    best_score = float('-inf') if color == 'white' else float('inf')
    
    for from_square, to_square in all_moves:
        # Make move
        original_board = copy.deepcopy(board)
        from_row, from_col = from_square
        to_row, to_col = to_square
        board[to_row][to_col] = board[from_row][from_col]
        board[from_row][from_col] = '.'
        
        # Evaluate using minimax
        score = minimax(depth - 1, color == 'black')
        
        # Undo
        board = copy.deepcopy(original_board)
        
        # Check if best
        if color == 'white':
            if score > best_score:
                best_score = score
                best_move = (from_square, to_square)
        else:
            if score < best_score:
                best_score = score
                best_move = (from_square, to_square)
    
    return best_move
#===========================================================================TERMINAL BOARD===========================================================================
print("GAME STARTED")
for row in board:
    print(row)
#===========================================================================MAIN GAME LOOP===========================================================================
run = True
clock = pygame.time.Clock()
images_loaded = load_images()
while run:
    
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            run = False
            continue
        if promotion_pending:
            if event.type == pygame.QUIT:
                run = False
                continue
            if event.type == pygame.MOUSEBUTTONDOWN:
                x, y = event.pos
                for i, p in enumerate(['Q', 'R', 'B', 'N']):
                    button_x = 80 + i * 140
                    button_rect = pygame.Rect(button_x, height // 2, 120, 120)
                    if button_rect.collidepoint(x, y):
                        row, col = promotion_pending
                        promote_pawn(row, col, p)
                        promotion_pending = None
                        switch_turn()
                        break
            continue

        if event.type == pygame.MOUSEBUTTONDOWN:

            if game_over:
                run = False
                continue

            mouse_pos = event.pos
            if mouse_pos[0] >= board_width:
                continue
            clicked_square = get_square_from_mouse(mouse_pos)

            if clicked_square:
                row, col = clicked_square
                piece = board[row][col]
                if selected_square is None:
                    if piece != '.' and is_current_player_piece(piece):
                        selected_square = clicked_square
                        valid_moves = get_valid_moves(row , col)
                        print(f"Selected: {Files[col]}{8 - row} - {get_piece_name(piece)}")
                        print(f"Legal moves: {len(valid_moves)}")
                        if len(valid_moves) == 0:
                            print("This piece has no legal moves")
                    elif piece != '.':
                        print(f"It's {current_turn}'s turn! Can't select opponent's piece.")
                    else:
                        print("Empty square. Select a piece first.")
                else:
                    from_row,from_col = selected_square
                    selected_piece = board[from_row][from_col]
                    if clicked_square == selected_square:
                        selected_square = None
                        valid_moves = []
                        print("piece deselected")
                    elif piece != '.' and is_current_player_piece(piece):
                        selected_square = clicked_square
                        valid_moves = get_valid_moves(row , col)
                        print(f"Switched selection to: {Files[col]}{8 - row} - {get_piece_name(piece)}")
                        print(f"Legal moves: {len(valid_moves)}")
                    else:
                        if clicked_square in valid_moves:
                            move_piece(selected_square,clicked_square)
                            selected_square = None
                            valid_moves = []
                            # Only switch turn if promotion is not pending
                            if not promotion_pending:
                                switch_turn()
                        else:
                            print("Invalid move! That's not a legal move.")
    
        # Update animation
        update_animation()
        
        # AI's turn - only after animation completes
        if current_turn == 'black' and not animating_move:
            move = get_best_move_minimax('black')
            if move:
                from_square, to_square = move
                move_piece(from_square, to_square)
                if not promotion_pending:
                    switch_turn()

    draw_board()
    draw_pieces()
    # draw_info()
    draw_right_panel()
    draw_game_over()
    draw_promotion_ui()

    pygame.display.flip()
    clock.tick(60)
#===========================================================================CLEANUP AND HISTORY===========================================================================
print("GAME ENDED")
print(f"Total moves made: {len(move_history)}")
if move_history:
    print("-"*50)
    print("\nMove history:")
    for i, move in enumerate(move_history, 1):
        color = "White" if i % 2 == 1 else "Black"
        print(f"  {(i+1)//2}. {color}: {move}")
pygame.quit()
sys.exit()