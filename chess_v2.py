import pygame
import sys
import copy
import os
import random
import time
#===========================================================================INTIALIZING PYGAME===========================================================================
pygame.init()
pygame.mixer.init()
#===========================================================================CONSTANTS===========================================================================
board_width = 640
panel_width = 250
width = board_width + panel_width  # Total: 890px
height = 720
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
white_in_check_cached = False
black_in_check_cached = False
ai_is_thinking = False
sounds = {}
sound_enabled = True
# Move replay/history tracking
board_history = []  # List of board states at each move
game_state_history = []  # List of (captured_pieces, en_passant_target, piece_moved) at each move
current_move_index = -1  # -1 = live game, >= 0 = replaying a past move
replay_animations = []  # List of (from_pos, to_pos, piece, start_time) for animated replay moves
#===========================================================================TIME CONTROL===========================================================================
time_control = None
white_time_remaining = 0
black_time_remaining = 0
last_time_update = None
time_exceeded = None
# Search control globals for iterative deepening / time-limited search
search_start_time = None
search_time_limit = None
#===========================================================================ZOBRIST HASHING & MOVE HEURISTICS===========================================================================
# Zobrist hashing: random 64-bit numbers for piece-square, castling, en-passant and side-to-move.
ZOBRIST_PIECE = {}  # mapping piece_symbol -> list[64] of random ints
ZOBRIST_CASTLING = [0] * 6
ZOBRIST_EP = [0] * 8  # per file
ZOBRIST_SIDE = 0

# Current incremental Zobrist hash for the live board (keeps TT keys O(1) on make/undo)
current_zobrist = None

# History and killer heuristics
history_score = {}  # move tuple -> score (improves move ordering over time)
killer_moves = {}   # depth -> [killer1, killer2]

# Principal variation table for PV extraction
pv_table = {}

def init_zobrist(seed=0):
    """Initialize Zobrist random numbers.
    Quick comment: Zobrist gives an O(1) incremental hash for positions instead of building tuples.
    """
    global ZOBRIST_PIECE, ZOBRIST_CASTLING, ZOBRIST_EP, ZOBRIST_SIDE
    rnd = random.Random(seed)
    pieces = ['P','N','B','R','Q','K','p','n','b','r','q','k']
    for p in pieces:
        ZOBRIST_PIECE[p] = [rnd.getrandbits(64) for _ in range(64)]
    for i in range(6):
        ZOBRIST_CASTLING[i] = rnd.getrandbits(64)
    for i in range(8):
        ZOBRIST_EP[i] = rnd.getrandbits(64)
    ZOBRIST_SIDE = rnd.getrandbits(64)

def zobrist_hash(side=None):
    """Compute Zobrist hash for current board and given side-to-move (or current_turn).
    This is faster and compact compared to large tuple keys.
    """
    h = 0
    for r in range(8):
        for c in range(8):
            p = board[r][c]
            if p != '.':
                idx = r * 8 + c
                h ^= ZOBRIST_PIECE[p][idx]

    # Castling rights (6 booleans in piece_moved)
    flags = [
        piece_moved.get('white_king'),
        piece_moved.get('white_rook_a'),
        piece_moved.get('white_rook_h'),
        piece_moved.get('black_king'),
        piece_moved.get('black_rook_a'),
        piece_moved.get('black_rook_h')
    ]
    for i, f in enumerate(flags):
        if f:
            h ^= ZOBRIST_CASTLING[i]

    # En-passant file
    if en_passant_target is not None:
        _, ep_col = en_passant_target
        h ^= ZOBRIST_EP[ep_col]

    # Side to move
    side_to_move = current_turn if side is None else side
    if side_to_move == 'black':
        h ^= ZOBRIST_SIDE

    return h

def square_index(row, col):
    return row * 8 + col

def apply_zobrist_move(from_sq, to_sq, piece, captured_piece=None, capture_sq=None):
    """Apply XOR changes to `current_zobrist` for a simple move (non-castling, non-promotion).

    - `from_sq`, `to_sq`: (r,c)
    - `piece`: moving piece symbol (e.g., 'P' or 'n')
    - `captured_piece`: captured piece symbol if any
    - `capture_sq`: (r,c) where captured piece is located (used for en-passant)
    This function toggles side-to-move as well.
    """
    global current_zobrist
    if current_zobrist is None:
        # Fallback: compute full hash
        current_zobrist = zobrist_hash()

    fr, fc = from_sq
    tr, tc = to_sq
    fidx = square_index(fr, fc)
    tidx = square_index(tr, tc)

    # XOR out piece from source
    if piece is not None and piece != '.':
        current_zobrist ^= ZOBRIST_PIECE[piece][fidx]

    # XOR out captured piece at its square (if capture_sq given use that, else use target square)
    if captured_piece and captured_piece != '.':
        if capture_sq:
            cidx = square_index(capture_sq[0], capture_sq[1])
        else:
            cidx = tidx
        current_zobrist ^= ZOBRIST_PIECE[captured_piece][cidx]

    # XOR in piece at target
    if piece is not None and piece != '.':
        current_zobrist ^= ZOBRIST_PIECE[piece][tidx]

    # Toggle side to move
    current_zobrist ^= ZOBRIST_SIDE

def init_current_zobrist():
    global current_zobrist
    current_zobrist = zobrist_hash()

def get_principal_variation(max_len=20):
    """Extract PV from `pv_table` starting at current position.

    PV extraction: follow stored best moves from transposition/PV table to build principal variation.
    """
    pv = []
    seen = set()
    side = current_turn
    key = position_hash(side)
    while len(pv) < max_len and key in pv_table and pv_table[key] is not None:
        mv = pv_table[key]
        if mv in seen:
            break
        pv.append(mv)
        seen.add(mv)
        # make the move on a temporary simulation to advance key
        (from_sq, to_sq) = mv
        fr, fc = from_sq
        tr, tc = to_sq
        piece = board[fr][fc]
        captured = board[tr][tc]
        # apply incremental Zobrist for the simulated move
        try:
            apply_zobrist_move((fr, fc), (tr, tc), piece, captured)
        except Exception:
            pass
        board[tr][tc] = piece
        board[fr][fc] = '.'
        # advance side
        side = 'black' if side == 'white' else 'white'
        key = position_hash(side)
        # undo
        board[fr][fc] = piece
        board[tr][tc] = captured
        try:
            apply_zobrist_move((fr, fc), (tr, tc), piece, captured)
        except Exception:
            pass

    return pv

#===========================================================================DRAW DETECTION===========================================================================
# Position repetition tracking and 50-move rule
position_history = {}
halfmove_clock = 0  # Counts halfmoves since last pawn move or capture
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
animation_duration = 0.4  # Faster, snappier animations
evaluation_history = []  
current_evaluation = 0 
transposition_table = {}
# Cache for legal moves to avoid recalculating
_legal_moves_cache = {}
_cache_board_hash = None
# Move replay feature
move_history_rects = {}  # Maps move_index -> pygame.Rect for click detection
replay_button_rects = {}  # Maps button_name -> pygame.Rect for control buttons
# Enhanced animation variables
piece_scale_animation = None  # For piece selection scaling
hover_square = None  # For hover effects
game_mode = None  # 'ai' or 'two_player'
"""===========================================================================DRAW BOARD==========================================================================="""
def draw_board():
    for row in range(8):
        for col in range(8):
            x = col * square_size
            y = row * square_size
            if (row + col) % 2 == 0:
                color = Light_square
            else:
                color = Dark_square
            
            # Apply hover effect
            if hover_square and hover_square == (row, col) and board[row][col] != '.':
                color = tuple(min(255, c + 15) for c in color)
            
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
                if (piece_color == 'white' and white_in_check_cached) or (piece_color == 'black' and black_in_check_cached):
                    color = Check_color

            pygame.draw.rect(screen , color , (x , y , square_size , square_size))

            if (row , col) in valid_moves:
                center_x = x + square_size // 2
                center_y = y + square_size // 2
                target = board[row][col]
                if target == '.':
                    # Larger and more visible dot for empty squares
                    pygame.draw.circle(screen, (150, 200, 150), (center_x, center_y), 14)
                    pygame.draw.circle(screen, (100, 150, 100), (center_x, center_y), 12, 2)
                else:
                    # Outer ring for capture squares
                    pygame.draw.circle(screen, (220, 150, 150), (center_x, center_y), 40, 4)
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
            
            # Apply scale effect to selected piece
            scale = 1.0
            if selected_square and selected_square == (row, col):
                scale = 1.05  # Slightly larger selected piece
            
            if images_loaded and piece in piece_images:
                image = piece_images[piece]
                if scale != 1.0:
                    new_size = int(square_size * scale)
                    image = pygame.transform.scale(image, (new_size, new_size))
                rect = image.get_rect(center=(center_x, center_y))
                # Add shadow effect for selected piece
                if selected_square and selected_square == (row, col):
                    shadow = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
                    pygame.draw.ellipse(shadow, (0, 0, 0, 40), shadow.get_rect())
                    screen.blit(shadow, rect)
                screen.blit(image, rect)
            else:
                symbol = piece_symbols[piece]
                text_color = White if piece.isupper() else Black
                text_surface = font.render(symbol, True, text_color)
                text_rect = text_surface.get_rect(center=(center_x, center_y))
                screen.blit(text_surface, text_rect)
    
    # Draw replay animations (multiple pieces moving simultaneously)
    for anim in replay_animations[:]:  # Copy list to allow modification during iteration
        from_row, from_col = anim['from']
        to_row, to_col = anim['to']
        piece = anim['piece']
        start_time = anim['start_time']
        
        # Calculate animation progress
        elapsed = (pygame.time.get_ticks() - start_time) / 1000.0
        progress = ease_in_out(min(elapsed / animation_duration, 1.0))
        
        from_x = from_col * square_size + square_size // 2
        from_y = from_row * square_size + square_size // 2
        to_x = to_col * square_size + square_size // 2
        to_y = to_row * square_size + square_size // 2
        
        current_x = from_x + (to_x - from_x) * progress
        current_y = from_y + (to_y - from_y) * progress
        
        # Draw animated piece
        if images_loaded and piece in piece_images:
            image = piece_images[piece]
            # Slight scale up for visibility
            scale = 1.05
            new_size = int(square_size * scale)
            scaled_image = pygame.transform.scale(image, (new_size, new_size))
            rect = scaled_image.get_rect(center=(int(current_x), int(current_y)))
            screen.blit(scaled_image, rect)
        else:
            symbol = piece_symbols[piece]
            text_color = White if piece.isupper() else Black
            text_surface = font.render(symbol, True, text_color)
            text_rect = text_surface.get_rect(center=(int(current_x), int(current_y)))
            screen.blit(text_surface, text_rect)
        
        # Remove animation when done
        if progress >= 1.0:
            replay_animations.remove(anim)
    
    # Draw main animated piece with shadow (for live game moves)
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
        
        # Draw shadow that fades with movement
        shadow_offset = int(5 * (1 - progress))
        if shadow_offset > 0:
            shadow_alpha = int(60 * (1 - progress))
            shadow_color = (0, 0, 0, shadow_alpha)
            pygame.draw.ellipse(screen, shadow_color, (current_x - square_size // 3, 
                                                        current_y + square_size // 3 - shadow_offset, 
                                                        square_size // 1.5, 8))
        
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
    overlay.set_alpha(200)  # More opaque for better readability
    overlay.fill((0, 0, 0))
    screen.blit(overlay, (0, 0))

    # Draw winning result with better styling
    result_surface = large_font.render(game_result, True, (255, 215, 0))  # Gold color
    result_rect = result_surface.get_rect(center=(width // 2, height // 2 - 60))
    
    # Add shadow effect
    shadow_surface = large_font.render(game_result, True, (0, 0, 0))
    shadow_rect = shadow_surface.get_rect(center=(width // 2 + 2, height // 2 - 58))
    screen.blit(shadow_surface, shadow_rect)
    screen.blit(result_surface, result_rect)

    instruction = "Click anywhere to close"
    instr_surface = small_font.render(instruction, True, (200, 200, 200))
    instr_rect = instr_surface.get_rect(center=(width // 2, height // 2 + 60))
    screen.blit(instr_surface, instr_rect)
"""===========================================================================DRAW PROMOTION==========================================================================="""
def draw_promotion_ui():
    if not promotion_pending:
        return
    
    # Overlay
    overlay = pygame.Surface((width, height))
    overlay.set_alpha(220)  # More opaque
    overlay.fill((0, 0, 0))
    screen.blit(overlay, (0, 0))
    
    # Title with shadow
    title = "Promote Pawn - Choose:"
    title_surface = font.render(title, True, (255, 215, 0))
    title_shadow = font.render(title, True, (0, 0, 0))
    title_rect = title_surface.get_rect(center=(width // 2, height // 2 - 130))
    title_shadow_rect = title_shadow.get_rect(center=(width // 2 + 2, height // 2 - 128))
    screen.blit(title_shadow, title_shadow_rect)
    screen.blit(title_surface, title_rect)
    
    # Buttons for Q, R, B, N
    row, col = promotion_pending
    is_white = board[row][col].isupper()
    pieces = [('Q', 'Queen'), ('R', 'Rook'), ('B', 'Bishop'), ('N', 'Knight')]
    
    button_y = height // 2 - 20
    for i, (p, name) in enumerate(pieces):
        x = 100 + i * 160
        button_rect = pygame.Rect(x, button_y, 120, 120)
        
        # Button background with gradient effect
        pygame.draw.rect(screen, (60, 60, 80), button_rect)
        pygame.draw.rect(screen, (150, 150, 180), button_rect, 3)
        
        # Use piece image if available, otherwise fall back to symbol
        piece_key = p if is_white else p.lower()
        if images_loaded and piece_key in piece_images:
            image = piece_images[piece_key]
            scaled = pygame.transform.scale(image, (90, 90))
            image_rect = scaled.get_rect(center=(button_rect.centerx, button_rect.centery - 15))
            screen.blit(scaled, image_rect)
        else:
            symbol = piece_symbols[piece_key]
            text = large_font.render(symbol, True, White if is_white else Black)
            text_rect = text.get_rect(center=(button_rect.centerx, button_rect.centery - 15))
            screen.blit(text, text_rect)
        
        # Piece name label
        label = tiny_font.render(name, True, (200, 200, 200))
        label_rect = label.get_rect(center=(button_rect.centerx, button_rect.centery + 40))
        screen.blit(label, label_rect)
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
"""===========================================================================JUMP TO MOVE==========================================================================="""
def jump_to_move(move_index):
    """Restore board state to a specific move in history (for replay).
    
    move_index: -1 = live game, 0+ = replay state after move N
    Creates animations to show the transition smoothly.
    """
    global board, board_history, game_state_history, current_move_index
    global captured_pieces, en_passant_target, piece_moved, halfmove_clock
    global current_turn, selected_square, valid_moves, _legal_moves_cache, current_zobrist
    global replay_animations
    
    # Save current board before change (for animation)
    board_before = [row[:] for row in board]
    
    # Clamp index
    if move_index < -1:
        move_index = -1
    if move_index >= len(board_history):
        move_index = len(board_history) - 1
    
    current_move_index = move_index
    
    if move_index == -1:
        # Return to live game (just mark as live, don't restore state)
        _legal_moves_cache.clear()
        selected_square = None
        valid_moves = []
        replay_animations = []
        return
    
    # Restore board state from history
    board = [row[:] for row in board_history[move_index]]
    state = game_state_history[move_index]
    captured_pieces = state['captured_pieces'].copy()
    captured_pieces['white'] = state['captured_pieces']['white'][:]
    captured_pieces['black'] = state['captured_pieces']['black'][:]
    en_passant_target = state['en_passant_target']
    piece_moved = state['piece_moved'].copy()
    halfmove_clock = state['halfmove_clock']
    
    # Recalculate current turn based on move count (move 0 = after white's 1st move, so black's turn)
    current_turn = 'black' if (move_index % 2) == 0 else 'white'
    
    # Recalculate current_zobrist for the restored state
    current_zobrist = zobrist_hash()
    
    # Generate animations for pieces that moved
    replay_animations = []
    start_time = pygame.time.get_ticks()
    
    for r in range(8):
        for c in range(8):
            piece_before = board_before[r][c]
            piece_after = board[r][c]
            
            # If a piece was here before but not now, it moved away
            if piece_before != '.' and piece_before != piece_after:
                # Find where this piece moved to
                for tr in range(8):
                    for tc in range(8):
                        if board_before[tr][tc] == '.' and board[tr][tc] == piece_before:
                            # Found it! Piece moved from (r,c) to (tr,tc)
                            anim = {
                                'from': (r, c),
                                'to': (tr, tc),
                                'piece': piece_before,
                                'start_time': start_time
                            }
                            replay_animations.append(anim)
                            break
    
    _legal_moves_cache.clear()
    selected_square = None
    valid_moves = []
"""===========================================================================DRAW MOVE HISTORY==========================================================================="""
def draw_move_history():
    """Draw scrollable, clickable move history with replay support."""
    global move_history_rects, replay_button_rects  # Store rects for click detection
    move_history_rects = {}  # Dict: move_index -> pygame.Rect
    replay_button_rects = {}  # Dict: button_name -> pygame.Rect
    
    hist_x = board_width + 15
    # If clocks are enabled, reserve space at top for them
    if time_control is not None and time_control != 'no_clock':
        hist_y = 130
        hist_height = 180
    else:
        hist_y = 20
        hist_height = 250
    hist_width = 220
    
    # Background with border
    hist_rect = pygame.Rect(hist_x, hist_y, hist_width, hist_height)
    pygame.draw.rect(screen, (25, 25, 35), hist_rect)
    pygame.draw.rect(screen, Panel_border, hist_rect, 2)
    
    # Title with icon
    title_surface = small_font.render("♟ Moves", True, (200, 180, 150))
    screen.blit(title_surface, (hist_x + 10, hist_y + 8))
    
    if not move_history:
        no_moves = tiny_font.render("No moves yet", True, (150, 150, 150))
        screen.blit(no_moves, (hist_x + 10, hist_y + 50))
        return
    
    # Draw moves with improved formatting
    y_offset = hist_y + 35
    move_height = 18
    
    # Calculate which moves to show (fits better now)
    start_idx = max(0, len(move_history) - 32)  # 16 pairs = 32 moves
    
    for i in range(start_idx, len(move_history), 2):
        if y_offset > hist_y + hist_height - 50:  # Reserve space for buttons
            break
        
        move_num = (i // 2) + 1
        white_move = move_history[i]
        black_move = move_history[i + 1] if i + 1 < len(move_history) else ""
        
        # Determine if this move pair is currently replayed or live
        white_idx = i  # Index in move_history
        black_idx = i + 1
        is_white_current = (current_move_index == white_idx)
        is_black_current = (current_move_index == black_idx)
        is_last_pair = (i >= len(move_history) - 2)
        
        # Highlight background based on state
        highlight_rect = pygame.Rect(hist_x + 3, y_offset - 1, hist_width - 6, move_height)
        if is_white_current or is_black_current:
            # Replay highlight (bright blue)
            pygame.draw.rect(screen, (80, 150, 200), highlight_rect)
            pygame.draw.rect(screen, (150, 200, 255), highlight_rect, 1)
        elif is_last_pair and current_move_index == -1:
            # Live game (last pair, not replaying)
            pygame.draw.rect(screen, (100, 120, 140), highlight_rect)
            pygame.draw.rect(screen, (150, 180, 200), highlight_rect, 1)
        
        # Move number
        num_surface = tiny_font.render(f"{move_num}.", True, (200, 160, 100))
        screen.blit(num_surface, (hist_x + 8, y_offset))
        
        # White's move (clickable)
        white_surface = tiny_font.render(white_move, True, (255, 240, 200))
        white_rect = pygame.Rect(hist_x + 32, y_offset - 1, 85, move_height)
        move_history_rects[white_idx] = white_rect
        screen.blit(white_surface, (hist_x + 32, y_offset))
        
        # Black's move (clickable if exists)
        if black_move:
            black_surface = tiny_font.render(black_move, True, (200, 200, 200))
            black_rect = pygame.Rect(hist_x + 128, y_offset - 1, 85, move_height)
            move_history_rects[black_idx] = black_rect
            screen.blit(black_surface, (hist_x + 128, y_offset))
        
        y_offset += move_height
    
    # Draw replay control buttons at bottom
    button_y = hist_y + hist_height - 40
    button_height = 28
    button_width = 50
    spacing = 8
    
    # "< Prev" button
    prev_x = hist_x + 10
    prev_rect = pygame.Rect(prev_x, button_y, button_width, button_height)
    prev_enabled = (current_move_index > -1)  # Can go back if not at live
    prev_color = (100, 150, 200) if prev_enabled else (60, 60, 80)
    pygame.draw.rect(screen, prev_color, prev_rect)
    pygame.draw.rect(screen, (150, 200, 255) if prev_enabled else (100, 100, 120), prev_rect, 1)
    prev_text = tiny_font.render("◄ Prev", True, (255, 255, 255) if prev_enabled else (120, 120, 120))
    prev_text_rect = prev_text.get_rect(center=prev_rect.center)
    screen.blit(prev_text, prev_text_rect)
    replay_button_rects['prev'] = prev_rect
    
    # "Live" button (go to latest)
    live_x = prev_x + button_width + spacing
    live_rect = pygame.Rect(live_x, button_y, button_width, button_height)
    live_enabled = (current_move_index != -1)  # Can go to live if replaying
    live_color = (200, 150, 100) if live_enabled else (60, 60, 80)
    pygame.draw.rect(screen, live_color, live_rect)
    pygame.draw.rect(screen, (255, 200, 150) if live_enabled else (100, 100, 120), live_rect, 1)
    live_text = tiny_font.render("Live", True, (255, 255, 255) if live_enabled else (120, 120, 120))
    live_text_rect = live_text.get_rect(center=live_rect.center)
    screen.blit(live_text, live_text_rect)
    replay_button_rects['live'] = live_rect
    
    # "Next >" button
    next_x = live_x + button_width + spacing
    next_rect = pygame.Rect(next_x, button_y, button_width, button_height)
    next_enabled = (current_move_index < len(move_history) - 1)  # Can go forward if not at last
    next_color = (100, 150, 200) if next_enabled else (60, 60, 80)
    pygame.draw.rect(screen, next_color, next_rect)
    pygame.draw.rect(screen, (150, 200, 255) if next_enabled else (100, 100, 120), next_rect, 1)
    next_text = tiny_font.render("Next ►", True, (255, 255, 255) if next_enabled else (120, 120, 120))
    next_text_rect = next_text.get_rect(center=next_rect.center)
    screen.blit(next_text, next_text_rect)
    replay_button_rects['next'] = next_rect
    
    # Display current move index
    if current_move_index == -1:
        move_label = "Live Game"
    else:
        move_label = f"Move {current_move_index + 1}/{len(move_history)}"
    move_label_surface = tiny_font.render(move_label, True, (180, 180, 180))
    screen.blit(move_label_surface, (hist_x + 10, button_y + button_height + 5))
"""===========================================================================DRAW CAPTURED PIECES PANEL==========================================================================="""
def draw_captured_pieces_panel():
    """Draw captured pieces in panel"""
    cap_x = board_width + 15
    cap_y = 335
    cap_width = 220
    cap_height = 140
    
    # Background with border
    cap_rect = pygame.Rect(cap_x, cap_y, cap_width, cap_height)
    pygame.draw.rect(screen, (25, 25, 35), cap_rect)
    pygame.draw.rect(screen, Panel_border, cap_rect, 2)
    
    # Title with icon
    title_surface = small_font.render("⚔ Captures", True, (220, 140, 140))
    screen.blit(title_surface, (cap_x + 10, cap_y + 8))
    
    # Black's pieces captured
    black_label = tiny_font.render("White captured:", True, (180, 180, 200))
    screen.blit(black_label, (cap_x + 10, cap_y + 38))
    
    x_offset = cap_x + 10
    y_offset = cap_y + 58
    for piece in captured_pieces['black']:
        if piece == '.':
            continue
        if images_loaded and piece in piece_images:
            small_img = pygame.transform.scale(piece_images[piece], (18, 18))
            screen.blit(small_img, (x_offset, y_offset))
        else:
            symbol = piece_symbols.get(piece, '')
            if symbol:
                text = tiny_font.render(symbol, True, Black)
                screen.blit(text, (x_offset, y_offset))
        x_offset += 22
        if x_offset > cap_x + cap_width - 25:
            x_offset = cap_x + 10
            y_offset += 20
    
    # White's pieces captured
    white_label = tiny_font.render("Black captured:", True, (200, 200, 150))
    screen.blit(white_label, (cap_x + 10, cap_y + 95))
    
    x_offset = cap_x + 10
    y_offset = cap_y + 115
    for piece in captured_pieces['white']:
        if piece == '.':
            continue
        if images_loaded and piece in piece_images:
            small_img = pygame.transform.scale(piece_images[piece], (18, 18))
            screen.blit(small_img, (x_offset, y_offset))
        else:
            symbol = piece_symbols.get(piece, '')
            if symbol:
                text = tiny_font.render(symbol, True, White)
                screen.blit(text, (x_offset, y_offset))
        x_offset += 22
        if x_offset > cap_x + cap_width - 25:
            break
"""===========================================================================DRAW GAME INFO PANEL==========================================================================="""
def draw_game_info_panel():
    """Draw current game status"""
    info_x = board_width + 15
    info_y = 590
    info_width = 220
    
    # Background with border
    info_rect = pygame.Rect(info_x, info_y, info_width, height - info_y - 5)
    pygame.draw.rect(screen, (25, 25, 35), info_rect)
    pygame.draw.rect(screen, Panel_border, info_rect, 2)
    
    # Title
    title_surface = small_font.render("⚙ Status", True, (180, 200, 150))
    screen.blit(title_surface, (info_x + 10, info_y + 8))
    
    # Turn indicator with color coding
    turn_text = f"Turn: {current_turn.capitalize()}"
    if is_in_check(current_turn):
        turn_text += " ⚠"
        turn_color = (255, 100, 100)
        # Draw a pulsing effect indicator
        pulse = int(abs(pygame.time.get_ticks() % 1000 - 500) / 250)
        pygame.draw.rect(screen, (255, 50, 50), (info_x + 8, info_y + 38, 16 + pulse * 2, 2))
    else:
        turn_color = (200, 200, 150) if current_turn == 'white' else (150, 150, 200)
    
    turn_surface = small_font.render(turn_text, True, turn_color)
    screen.blit(turn_surface, (info_x + 10, info_y + 35))
    
    # Material count
    white_material = count_material('white')
    black_material = count_material('black')
    advantage = white_material - black_material
    
    if advantage > 0:
        mat_text = f"Material: White +{advantage}"
        mat_color = (200, 200, 150)
    elif advantage < 0:
        mat_text = f"Material: Black +{abs(advantage)}"
        mat_color = (150, 150, 200)
    else:
        mat_text = "Material: Equal"
        mat_color = (180, 180, 180)
    
    mat_surface = tiny_font.render(mat_text, True, mat_color)
    screen.blit(mat_surface, (info_x + 10, info_y + 70))
    
    # Move count
    move_count_text = f"Total Moves: {len(move_history)}"
    move_surface = tiny_font.render(move_count_text, True, (180, 180, 180))
    screen.blit(move_surface, (info_x + 10, info_y + 95))

    button_x = info_x
    button_y = info_y + 70
    button_width = 100
    button_height = 35

    new_game_rect = pygame.Rect(button_x , button_y , button_width , button_height)
    pygame.draw.rect(screen , (60 , 130 , 60) , new_game_rect)
    pygame.draw.rect(screen , White , new_game_rect , 2)

    button_text = tiny_font.render("NEW GAME", True, White)
    button_text_rect = button_text.get_rect(center=new_game_rect.center)
    screen.blit(button_text, button_text_rect)

    return new_game_rect
"""===========================================================================DRAW RIGHT PANEL==========================================================================="""
def draw_right_panel():
    """Draw complete right panel with all components"""
    # Panel background with gradient effect
    panel_rect = pygame.Rect(board_width, 0, panel_width, height)
    pygame.draw.rect(screen, Panel_bg, panel_rect)
    
    # Add a subtle border/separator
    pygame.draw.line(screen, Panel_border, (board_width, 0), (board_width, height), 3)
    
    # Draw clocks first (only in two-player mode), then other components laid out beneath
    if game_mode == 'two_player':
        draw_clocks()
    draw_move_history()
    draw_captured_pieces_panel()
    new_game_button = draw_game_info_panel()

    return new_game_button
"""===========================================================================DRAW AI THINKING==========================================================================="""
def draw_ai_thinking_overlay():
    # Semi-transparent overlay
    overlay = pygame.Surface((width , height))
    overlay.set_alpha(180)
    overlay.fill((0 , 0 , 0))
    screen.blit(overlay , (0 , 0))
    # Main message
    thinking_text = large_font.render("AI THINKING...." , True , (255 , 200 , 0))
    thinking_rect = thinking_text.get_rect(center = (width // 2 , height // 2 - 40))
    screen.blit(thinking_text , thinking_rect)

    #Animating dots
    dots = "." * ((pygame.time.get_ticks() // 500) % 4)
    dots_text = small_font.render(dots, True, (200, 200, 200))
    dots_rect = dots_text.get_rect(center=(width // 2 + 80, height // 2 + 20))
    screen.blit(dots_text, dots_rect)
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
"""===========================================================================GET POSITION KEY==========================================================================="""
def get_position_key():
    """Create a hashable key describing the current position for repetition detection."""
    # Use board rows, current turn, castling rights (from piece_moved), and en_passant_target
    board_tuple = tuple(''.join(row) for row in board)
    castling = (
        piece_moved.get('white_king'),
        piece_moved.get('white_rook_a'),
        piece_moved.get('white_rook_h'),
        piece_moved.get('black_king'),
        piece_moved.get('black_rook_a'),
        piece_moved.get('black_rook_h')
    )
    ep = en_passant_target if en_passant_target is None else (en_passant_target[0], en_passant_target[1])
    return (board_tuple, current_turn, castling, ep)
"""===========================================================================THREEFOLD REPETITION==========================================================================="""
def is_threefold_repetition():
    key = get_position_key()
    return position_history.get(key, 0) >= 3
"""===========================================================================FIFTY MOVE RULE==========================================================================="""
def is_fifty_move_rule():
    return halfmove_clock >= 100  # 100 halfmoves = 50 full moves
"""===========================================================================INSUFFICIENT MATERIAL==========================================================================="""
def is_insufficient_material():
    """Basic insufficient material detection.
    Covers: K vs K, K+N vs K, K+B vs K, and K+B vs K+B when bishops on same color is not handled precisely here.
    """
    pieces = []
    for r in board:
        for p in r:
            if p != '.' and p.upper() != 'K':
                pieces.append(p)

    # No pieces except kings
    if not pieces:
        return True

    # Single minor piece only
    if len(pieces) == 1 and pieces[0].upper() in ('B', 'N'):
        return True

    # More advanced cases (both sides only bishops) could be added later
    return False
"""===========================================================================IS IN CHECK==========================================================================="""
def is_in_check(color):
    king_pos = find_king(color)
    if not king_pos:
        return False
    opponent = 'black' if color == 'white' else 'white'
    # Generate all opponent moves and see if any attack king
    for r in range(8):
        for c in range(8):
            p = board[r][c]
            if p == '.':
                continue
            if opponent == 'white' and not p.isupper():
                continue
            if opponent == 'black' and not p.islower():
                continue
            moves = get_piece_moves(r, c)
            if king_pos in moves:
                return True
    return False
"""===========================================================================IS STALEMATE==========================================================================="""
def is_stalemate():
    # No legal moves for current player and not in check
    for r in range(8):
        for c in range(8):
            p = board[r][c]
            if p == '.':
                continue
            if current_turn == 'white' and not p.isupper():
                continue
            if current_turn == 'black' and not p.islower():
                continue
            if get_valid_moves(r, c):
                return False
    return not is_in_check(current_turn)
"""===========================================================================CHECK DRAW CONDITIONS==========================================================================="""
def check_draw_conditions():
    global game_over, game_result
    if is_threefold_repetition():
        game_over = True
        game_result = 'Draw by threefold repetition.'
        return True
    if is_fifty_move_rule():
        game_over = True
        game_result = 'Draw by 50-move rule.'
        return True
    if is_insufficient_material():
        game_over = True
        game_result = 'Draw by insufficient material.'
        return True
    if is_stalemate():
        game_over = True
        game_result = 'Stalemate.'
        return True
    return False
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
    global en_passant_target , promotion_pending, _legal_moves_cache, transposition_table, halfmove_clock, position_history, current_zobrist
    global white_in_check_cached, black_in_check_cached

    from_row,from_col = from_square
    to_row,to_col = to_square
    start_animation(from_square , to_square)

    piece = board[from_row][from_col]
    captured_piece = board[to_row][to_col]
    # Save previous Zobrist-affecting state
    prev_en_passant = en_passant_target
    prev_piece_moved = piece_moved.copy()

    while update_animation():
        draw_board()
        draw_pieces()
        pygame.display.flip()
        clock.tick(60)
    
    if piece.upper() == 'K' and abs(to_col - from_col) == 2:
        execute_castling(from_row, from_col, to_col)
        update_pieces_moved(piece, from_row, from_col)
        play_sound('castle', volume=0.6)
        _legal_moves_cache.clear()
        transposition_table.clear()
        return True
    
    is_en_passant = False
    if piece.upper() == 'P' and to_col != from_col and board[to_row][to_col] == '.':
        is_en_passant = True
        captured_actual = board[from_row][to_col]
        capture_sq = (from_row, to_col)
    else:
        captured_actual = board[to_row][to_col]
        capture_sq = (to_row, to_col)

    # Update incremental Zobrist for this move (handles piece squares, captures, and side)
    try:
        apply_zobrist_move((from_row, from_col), (to_row, to_col), piece, captured_actual, capture_sq)
    except Exception:
        # if for any reason incremental hash isn't available, fall back later
        pass

    if is_en_passant:
        board[to_row][to_col] = piece
        board[from_row][from_col] = '.'
        board[from_row][to_col] = '.'  
        play_sound('pawn_capture', volume=0.6)
    else:
        board[to_row][to_col] = piece
        board[from_row][from_col] = '.'
        if captured_piece != '.':
            play_capture_sound(captured_piece, piece)  # ← ADD THIS
        else:
            play_move_sound(piece)
    
    update_pieces_moved(piece , from_row , from_col)
    _legal_moves_cache.clear()
    transposition_table.clear()

    # Update en-passant target and XOR EP changes into incremental hash
    en_passant_target = None
    if piece.upper() == 'P' and abs(to_row - from_row) == 2:
        ep_row = (from_row + to_row) // 2
        en_passant_target = (ep_row, to_col)

    # Apply en-passant Zobrist changes (old -> new)
    if current_zobrist is not None:
        # XOR out previous EP
        if prev_en_passant is not None:
            _, prev_col = prev_en_passant
            current_zobrist ^= ZOBRIST_EP[prev_col]
        # XOR in new EP
        if en_passant_target is not None:
            _, new_col = en_passant_target
            current_zobrist ^= ZOBRIST_EP[new_col]

    # Update castling-related Zobrist bits for any flags that changed from False->True
    if current_zobrist is not None:
        flag_keys = [
            'white_king', 'white_rook_a', 'white_rook_h',
            'black_king', 'black_rook_a', 'black_rook_h'
        ]
        for i, key in enumerate(flag_keys):
            if not prev_piece_moved.get(key, False) and piece_moved.get(key, False):
                current_zobrist ^= ZOBRIST_CASTLING[i]
    
    if piece.upper() == 'P':
        if (piece == 'P' and to_row == 0) or (piece == 'p' and to_row == 7):
            promotion_pending = (to_row, to_col)

    from_notation = f"{Files[from_col]}{8 - from_row}"
    to_notation = f"{Files[to_col]}{8 - to_row}"
    capture_happened = (captured_piece != '.')
    if capture_happened:
        if is_white_piece(captured_piece):
            captured_pieces['white'].append(captured_piece)
        else:
            captured_pieces['black'].append(captured_piece)
        move_str = f"{from_notation} x {to_notation}"
        print(f"Capture! {get_piece_name(piece)} takes {get_piece_name(captured_piece)}")
    else:
        move_str  = f"{from_notation} → {to_notation}"
    
    move_history.append(move_str)
    print(f"Move: {move_str}")
    current_evaluation = evaluate_board() / 100  # Convert to pawn units
    evaluation_history.append(current_evaluation)

    # Save board state for replay feature
    global board_history, game_state_history, current_move_index
    board_history.append([row[:] for row in board])  # Deep copy of current board
    game_state_history.append({
        'captured_pieces': {'white': captured_pieces['white'][:], 'black': captured_pieces['black'][:]},
        'en_passant_target': en_passant_target,
        'piece_moved': piece_moved.copy(),
        'halfmove_clock': halfmove_clock
    })
    current_move_index = len(board_history) - 1  # Set to latest move (live game)

    # Update halfmove clock: reset on pawn move or capture
    if piece.upper() == 'P' or capture_happened:
        halfmove_clock = 0
    else:
        halfmove_clock += 1

    # Record current position after move for repetition detection (key uses side to move after this move)
    next_turn = 'black' if current_turn == 'white' else 'white'
    board_tuple = tuple(''.join(row) for row in board)
    castling = (
        piece_moved.get('white_king'),
        piece_moved.get('white_rook_a'),
        piece_moved.get('white_rook_h'),
        piece_moved.get('black_king'),
        piece_moved.get('black_rook_a'),
        piece_moved.get('black_rook_h')
    )
    ep = en_passant_target if en_passant_target is None else (en_passant_target[0], en_passant_target[1])
    key = (board_tuple, next_turn, castling, ep)
    position_history[key] = position_history.get(key, 0) + 1

    # Check draw conditions (threefold, 50-move, insufficient material, stalemate)
    check_draw_conditions()
    # Update check cache
    white_in_check_cached = is_in_check('white')
    black_in_check_cached = is_in_check('black')
    
    # Update evaluation
    current_evaluation = evaluate_board() / 100
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
def is_square_attacked(row, col, by_color):
    """Optimized check if a square is attacked by a color."""
    # Check pawn attacks (simple early exit)
    # Pawns attack diagonally in the direction they move
    # White pawns move up (direction -1), so they attack FROM row+1 (below them)
    # Black pawns move down (direction +1), so they attack FROM row-1 (above them)
    if by_color == 'white':
        pawn_dirs = [(1, -1), (1, 1)]  # Pawns below the target square
    else:
        pawn_dirs = [(-1, -1), (-1, 1)]  # Pawns above the target square
    
    for d_row, d_col in pawn_dirs:
        check_row, check_col = row + d_row, col + d_col
        if is_on_board(check_row, check_col):
            piece = board[check_row][check_col]
            if piece.upper() == 'P' and ((piece.isupper() and by_color == 'white') or (piece.islower() and by_color == 'black')):
                return True
    
    # Check knight attacks
    knight_moves = [(-2, -1), (-2, 1), (-1, -2), (-1, 2), (1, -2), (1, 2), (2, -1), (2, 1)]
    for d_row, d_col in knight_moves:
        check_row, check_col = row + d_row, col + d_col
        if is_on_board(check_row, check_col):
            piece = board[check_row][check_col]
            if piece.upper() == 'N' and ((piece.isupper() and by_color == 'white') or (piece.islower() and by_color == 'black')):
                return True
    
    # Check sliding pieces (rooks, bishops, queens)
    directions = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]
    for d_row, d_col in directions:
        check_row, check_col = row + d_row, col + d_col
        while is_on_board(check_row, check_col):
            piece = board[check_row][check_col]
            if piece != '.':
                if (piece.isupper() and by_color == 'white') or (piece.islower() and by_color == 'black'):
                    piece_type = piece.upper()
                    if piece_type == 'Q':
                        return True
                    elif piece_type == 'R' and (d_row != 0 or d_col != 0) and not (d_row != 0 and d_col != 0):
                        return True
                    elif piece_type == 'B' and (d_row != 0 and d_col != 0):
                        return True
                break
            check_row += d_row
            check_col += d_col
    
    # Check king attacks
    king_moves = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
    for d_row, d_col in king_moves:
        check_row, check_col = row + d_row, col + d_col
        if is_on_board(check_row, check_col):
            piece = board[check_row][check_col]
            if piece.upper() == 'K' and ((piece.isupper() and by_color == 'white') or (piece.islower() and by_color == 'black')):
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
    
    from_row, from_col = from_square
    to_row, to_col = to_square
    
    # Save state
    captured = board[to_row][to_col]
    piece = board[from_row][from_col]
    
    # Make move
    # Incremental Zobrist update for simulated move
    try:
        apply_zobrist_move((from_row, from_col), (to_row, to_col), piece, captured)
    except Exception:
        pass
    board[to_row][to_col] = piece
    board[from_row][from_col] = '.'
    
    in_check = is_in_check(color)
    
    # Undo move
    board[from_row][from_col] = piece
    board[to_row][to_col] = captured
    try:
        apply_zobrist_move((from_row, from_col), (to_row, to_col), piece, captured)
    except Exception:
        pass
    
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
    global _legal_moves_cache, _cache_board_hash
    
    board_hash = position_hash()
    cache_key = (board_hash, color)
    
    # Return cached result if board hasn't changed
    if cache_key in _legal_moves_cache:
        return _legal_moves_cache[cache_key]
    
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
    
    _legal_moves_cache[cache_key] = all_moves
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
            play_sound('stalemate', volume=0.7)
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
    # Keep incremental Zobrist hash in sync with side-to-move
    global current_zobrist
    if current_zobrist is not None:
        current_zobrist ^= ZOBRIST_SIDE
    if is_in_check(current_turn):
        print(f"Check! {current_turn.capitalize()}'s king is under attack!")
        play_sound('check', volume=0.7)
    
    if not check_game_over():
        print(f"{current_turn.capitalize()}'s turn")
    
    print()
"""===========================================================================EVALUATE BOARD==========================================================================="""
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
def get_ordered_move(color, depth=3):
    """Return moves ordered by heuristic score.

    Uses MVV-LVA base score (`score_move`) plus history heuristic and killer move bonuses to
    improve alpha-beta pruning efficiency.
    """
    moves = get_all_legal_moves(color)

    move_scores = []
    killers = killer_moves.get(depth, [])
    for from_sq, to_sq in moves:
        base = score_move(from_sq, to_sq)
        # History heuristic: moves that caused cutoffs previously get higher score
        hist = history_score.get((from_sq, to_sq), 0)
        # Killer move bonus: if this move equals a killer at this depth
        killer_bonus = 0
        if killers:
            if (from_sq, to_sq) == killers[0]:
                killer_bonus = 1000
            elif len(killers) > 1 and (from_sq, to_sq) == killers[1]:
                killer_bonus = 800

        total = base + hist + killer_bonus
        move_scores.append((total, from_sq, to_sq))

    move_scores.sort(reverse=True, key=lambda x: x[0])
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
        from_row, from_col = from_square
        to_row, to_col = to_square
        
        # Simulate move - avoid deep copy
        captured = board[to_row][to_col]
        piece = board[from_row][from_col]
        try:
            apply_zobrist_move((from_row, from_col), (to_row, to_col), piece, captured)
        except Exception:
            pass
        board[to_row][to_col] = piece
        board[from_row][from_col] = '.'
        
        # Evaluate
        score = evaluate_board()
        
        # Restore board
        board[from_row][from_col] = piece
        board[to_row][to_col] = captured
        try:
            apply_zobrist_move((from_row, from_col), (to_row, to_col), piece, captured)
        except Exception:
            pass
        
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
def position_hash(side=None):
    """Create a unique hash for current board position.
    If `side` is provided, use that as the side-to-move for the key (used by search).
    """
    # If incremental `current_zobrist` is available use it (fast O(1)).
    # If side differs from `current_turn`, flip the side bit.
    global current_zobrist
    if current_zobrist is not None:
        if side is None or side == current_turn:
            return current_zobrist
        else:
            return current_zobrist ^ ZOBRIST_SIDE
    # Fallback: compute full Zobrist hash
    return zobrist_hash(side)
"""===========================================================================BEST MOVE ITERATIVE==========================================================================="""
def get_best_move_iterative(color, max_time=5.0):
    """
    Search with iterative deepening.
    
    max_time: Maximum seconds to think
    """
    global search_start_time, search_time_limit, transposition_table
    best_move = None
    start_time = time.time()
    search_start_time = start_time
    search_time_limit = max_time

    # Clear transposition table between full searches to avoid stale bounds
    transposition_table.clear()

    try:
        prev_score = 0
        for depth in range(1, 12):  # Try increasing depths
            if time.time() - start_time > max_time:
                break  # Out of time!

            # Aspiration window around previous score for faster searches
            window = 50  # centipawn window
            alpha = prev_score - window
            beta = prev_score + window
            while True:
                try:
                    move, score = minimax_root(color, depth, alpha, beta)
                    best_move = move
                    prev_score = score
                    print(f"Depth {depth}: score {score}, move {move}")
                    break
                except TimeoutError:
                    raise
                except Exception:
                    # If result is outside window or other failure, expand window and retry
                    window *= 2
                    alpha = prev_score - window
                    beta = prev_score + window
                    if window > 10000:
                        break
    finally:
        search_start_time = None
        search_time_limit = None

    return best_move
"""===========================================================================MINIMAX ROOT==========================================================================="""
def minimax_root(color, depth, alpha=float('-inf'), beta=float('inf')):
    """Top-level minimax that returns best move."""
    global board
    moves = get_ordered_move(color, depth)
    best_move = moves[0] if moves else None
    best_score = float('-inf') if color == 'white' else float('inf')
    
    alpha = float('-inf')
    beta = float('inf')
    
    for move in moves:
        from_sq, to_sq = move
        from_row, from_col = from_sq
        to_row, to_col = to_sq
        
        # Make move - store what was captured for undo
        captured = board[to_row][to_col]
        piece = board[from_row][from_col]
        # Update incremental Zobrist for this move
        try:
            apply_zobrist_move((from_row, from_col), (to_row, to_col), piece, captured)
        except Exception:
            pass
        board[to_row][to_col] = piece
        board[from_row][from_col] = '.'

        # Recurse
        try:
            score = minimax(depth - 1, color == 'black', alpha, beta)
        except TimeoutError:
            # Undo and re-raise
            board[from_row][from_col] = piece
            board[to_row][to_col] = captured
            raise

        # Undo move - directly restore instead of deep copy
        board[from_row][from_col] = piece
        board[to_row][to_col] = captured
        # Revert incremental Zobrist for this move
        try:
            apply_zobrist_move((from_row, from_col), (to_row, to_col), piece, captured)
        except Exception:
            pass
        
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
            # store PV move for root
            pv_table[position_hash(color)] = best_move
            break
    
    # store PV at root
    pv_table[position_hash(color)] = best_move
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
    # Time cutoff for iterative deepening
    if search_start_time is not None and search_time_limit is not None:
        if time.time() - search_start_time > search_time_limit:
            raise TimeoutError()

    side = 'white' if is_maximizing else 'black'
    pos_hash = position_hash(side)
    if pos_hash in transposition_table:
        stored_depth, stored_score, stored_flag = transposition_table[pos_hash]
        if stored_depth >= depth:
            if stored_flag == 'EXACT':
                return stored_score
            elif stored_flag == 'LOWER':
                alpha = max(alpha, stored_score)
            elif stored_flag == 'UPPER':
                beta = min(beta, stored_score)
            if alpha >= beta:
                return stored_score

    if depth == 0:
        final_score = evaluate_board()
        transposition_table[pos_hash] = (depth, final_score, 'EXACT')
        return final_score
    
    legal_moves = get_ordered_move('white' if is_maximizing else 'black', depth)
    
    if not legal_moves:
        # Checkmate or stalemate
        if is_in_check('white' if is_maximizing else 'black'):
            final_score = -10000 if is_maximizing else 10000  # Checkmate
        else:
            final_score = 0  # Stalemate
        transposition_table[pos_hash] = (depth, final_score, 'EXACT')
        return final_score
    
    if is_maximizing:
        max_eval = float('-inf')
        best_move_local = None
        for from_square, to_square in legal_moves:
            from_row, from_col = from_square
            to_row, to_col = to_square
            
            # Make move - avoid deep copy
            captured = board[to_row][to_col]
            piece = board[from_row][from_col]
            # Incremental Zobrist update for this move
            try:
                apply_zobrist_move((from_row, from_col), (to_row, to_col), piece, captured)
            except Exception:
                pass
            board[to_row][to_col] = piece
            board[from_row][from_col] = '.'
            
            # Recurse
            try:
                eval = minimax(depth - 1, False, alpha, beta)
            except TimeoutError:
                raise
            
            # Undo move - direct restore
            board[from_row][from_col] = piece
            board[to_row][to_col] = captured
            # Revert incremental Zobrist update for this move
            try:
                apply_zobrist_move((from_row, from_col), (to_row, to_col), piece, captured)
            except Exception:
                pass
            
            if eval > max_eval:
                max_eval = eval
                best_move_local = (from_square, to_square)
            alpha = max(alpha, eval)
            if beta <= alpha:
                # Beta-cutoff: update history heuristic and killers
                mv = (from_square, to_square)
                # Do not count captures for history heuristic (optional)
                captured = board[to_row][to_col]
                if captured == '.':
                    history_score[mv] = history_score.get(mv, 0) + depth * depth
                # Update killer moves for this depth
                k = killer_moves.get(depth, [])
                if not k or k[0] != mv:
                    killer_moves[depth] = [mv] + (k[:1] if k else [])
                break  # Pruning
        
        # Store in transposition table with proper flag
        # Store PV and transposition info
        pv_table[pos_hash] = best_move_local
        if max_eval <= alpha:
            flag = 'UPPER'
        elif max_eval >= beta:
            flag = 'LOWER'
        else:
            flag = 'EXACT'
        transposition_table[pos_hash] = (depth, max_eval, flag)
        return max_eval
    
    else:
        min_eval = float('inf')
        best_move_local = None
        for from_square, to_square in legal_moves:
            from_row, from_col = from_square
            to_row, to_col = to_square
            
            # Make move - avoid deep copy
            captured = board[to_row][to_col]
            piece = board[from_row][from_col]
            # Incremental Zobrist update for this move
            try:
                apply_zobrist_move((from_row, from_col), (to_row, to_col), piece, captured)
            except Exception:
                pass
            board[to_row][to_col] = piece
            board[from_row][from_col] = '.'
            
            # Recurse
            try:
                eval = minimax(depth - 1, True, alpha, beta)
            except TimeoutError:
                raise
            
            # Undo move - direct restore
            board[from_row][from_col] = piece
            board[to_row][to_col] = captured
            # Revert incremental Zobrist update for this move
            try:
                apply_zobrist_move((from_row, from_col), (to_row, to_col), piece, captured)
            except Exception:
                pass
            
            if eval < min_eval:
                min_eval = eval
                best_move_local = (from_square, to_square)
            beta = min(beta, eval)
            if beta <= alpha:
                mv = (from_square, to_square)
                captured = board[to_row][to_col]
                if captured == '.':
                    history_score[mv] = history_score.get(mv, 0) + depth * depth
                k = killer_moves.get(depth, [])
                if not k or k[0] != mv:
                    killer_moves[depth] = [mv] + (k[:1] if k else [])
                break  # Pruning
        
        # Store in transposition table with proper flag
        pv_table[pos_hash] = best_move_local
        if min_eval <= alpha:
            flag = 'UPPER'
        elif min_eval >= beta:
            flag = 'LOWER'
        else:
            flag = 'EXACT'
        transposition_table[pos_hash] = (depth, min_eval, flag)
        return min_eval
"""===========================================================================GET BEST MOVE MINIMAX==========================================================================="""
def get_best_move_minimax(color, depth=5):
    """Get best move using minimax algorithm."""
    # Use minimax_root for consistent alpha-beta search
    move, score = minimax_root(color, depth)
    return move
"""===========================================================================FORMAT TIME==========================================================================="""
def format_time(seconds):
    mins = int(seconds) // 60
    secs = int(seconds) % 60
    return f"{mins}:{secs:02d}"
"""===========================================================================UPDATE CLOCKS==========================================================================="""
def update_clocks():
    global white_time_remaining, black_time_remaining, last_time_update, current_turn, time_exceeded, game_over, game_result
    
    if time_control == 'no_clock':
        return
    
    current_time = time.time()
    if last_time_update is None:
        last_time_update = current_time
        return
    
    time_delta = current_time - last_time_update
    last_time_update = current_time
    
    if current_turn == 'white':
        white_time_remaining -= time_delta
        if white_time_remaining <= 0:
            white_time_remaining = 0
            time_exceeded = 'white'
            game_over = True
            game_result = "Black won! White's time expired."
    else:
        black_time_remaining -= time_delta
        if black_time_remaining <= 0:
            black_time_remaining = 0
            time_exceeded = 'black'
            game_over = True
            game_result = "White won! Black's time expired."
"""===========================================================================DRAW CLOCKS==========================================================================="""
def draw_clocks():
    if time_control == 'no_clock':
        return
    
    clock_y = 10
    clock_x = board_width + 10
    clock_width = panel_width - 20
    clock_height = 50
    
    white_bg = (80, 80, 80) if current_turn != 'white' else (120, 120, 80)
    pygame.draw.rect(screen, white_bg, (clock_x, clock_y, clock_width, clock_height))
    pygame.draw.rect(screen, (200, 200, 200), (clock_x, clock_y, clock_width, clock_height), 2)
    
    white_time_text = format_time(white_time_remaining)
    white_time_surface = small_font.render(white_time_text, True, (255, 255, 100) if current_turn == 'white' else (200, 200, 200))
    white_time_rect = white_time_surface.get_rect(center=(clock_x + clock_width // 2, clock_y + clock_height // 2))
    screen.blit(white_time_surface, white_time_rect)
    
    black_clock_y = clock_y + clock_height + 5
    black_bg = (80, 80, 80) if current_turn != 'black' else (120, 120, 80)
    pygame.draw.rect(screen, black_bg, (clock_x, black_clock_y, clock_width, clock_height))
    pygame.draw.rect(screen, (200, 200, 200), (clock_x, black_clock_y, clock_width, clock_height), 2)
    
    black_time_text = format_time(black_time_remaining)
    black_time_surface = small_font.render(black_time_text, True, (255, 255, 100) if current_turn == 'black' else (200, 200, 200))
    black_time_rect = black_time_surface.get_rect(center=(clock_x + clock_width // 2, black_clock_y + clock_height // 2))
    screen.blit(black_time_surface, black_time_rect)
"""===========================================================================LOAD SOUNDS==========================================================================="""
def load_sounds():
    global sounds 
    sound_mapping = {
        'move' : 'chess-pieces-hitting-wooden-board-99336.wav',
        'horse_move' : 'Horse_Movement.wav',
        'elephant_move' : 'Elephant_Movement.wav',

        'capture': 'White_Captures_Piece.wav',
        'white_capture': 'White_Captures_Piece.wav',
        'black_capture': 'Black_Captures_Piece.wav',
        'pawn_capture': 'Pawn_Capture.wav',
        'queen_capture': 'Queen_Capture.wav',

        'check': 'Check.wav',
        'checkmate': 'Black_Checkmate.wav',
        'stalemate': 'Stalemate.wav',
        'ai_thinking': 'AI_Thinking.wav',

        'castle': 'chess-pieces-hitting-wooden-board-99336.wav', 
        'promote': 'chess-pieces-hitting-wooden-board-99336.wav',
    }

    sound_loaded = True
    loaded_count = 0

    for sound_name , filename in sound_mapping.items():
        path = os.path.join('assets', 'Sounds', filename)
        try:
            sounds[sound_name] = pygame.mixer.Sound(path)
            print(f"✓ Loaded: {sound_name}")
            loaded_count += 1
        except (pygame.error , FileNotFoundError) as e:
            print(f"✗ Failed to load {sound_name}: {e}")
            sounds[sound_name] = None
            sounds_loaded = False
    
    return sound_loaded
"""===========================================================================PLAY SOUNDS==========================================================================="""
def play_sound(sound_name , volume = 1.0):
    if sound_name in sounds and sounds[sound_name]:
        sound = sounds[sound_name]
        sound.set_volume(volume)
        sound.play()
"""===========================================================================PLAY MOVE SOUNDS==========================================================================="""
def play_move_sound(piece):
    piece_upper = piece.upper()
    
    if piece_upper == 'N':
        play_sound('horse_move')
    elif piece_upper == 'R':
        play_sound('elephant_move')
    else:
        play_sound('move')
"""===========================================================================PLAY CAPTURE SOUNDS==========================================================================="""
def play_capture_sound(captured_piece, capturing_piece):
    captured_upper = captured_piece.upper()
    capturing_upper = capturing_piece.upper()
    
    if captured_upper == 'Q':
        play_sound('queen_capture')
    elif capturing_upper == 'P':
        play_sound('pawn_capture')
    elif capturing_piece.isupper():
        play_sound('white_capture')
    else:
        play_sound('black_capture')
"""===========================================================================SET MASTER VOLUME==========================================================================="""
def set_master_volume(volume):
    volume = max(0.0, min(1.0, volume))
    for sound in sounds.values():
        if sound:
            sound.set_volume(volume)
"""===========================================================================RESET GAME==========================================================================="""
def reset_game():
    """Reset all game state to start a new game."""
    global board, selected_square, current_turn, move_history, valid_moves
    global game_over, game_result, piece_moved, en_passant_target, promotion_pending
    global captured_pieces, animating_move, evaluation_history, current_evaluation
    global white_in_check_cached, black_in_check_cached
    global board_history, game_state_history, current_move_index
    global position_history, halfmove_clock, transposition_table, pv_table
    global history_score, killer_moves
    global white_time_remaining, black_time_remaining, last_time_update, time_exceeded
    
    print("\n" + "="*50)
    print("RESETTING GAME...")
    print("="*50)
    
    # Reset board
    board = [
        ['r', 'n', 'b', 'q', 'k', 'b', 'n', 'r'],
        ['p', 'p', 'p', 'p', 'p', 'p', 'p', 'p'],
        ['.', '.', '.', '.', '.', '.', '.', '.'],
        ['.', '.', '.', '.', '.', '.', '.', '.'],
        ['.', '.', '.', '.', '.', '.', '.', '.'],
        ['.', '.', '.', '.', '.', '.', '.', '.'],
        ['P', 'P', 'P', 'P', 'P', 'P', 'P', 'P'],
        ['R', 'N', 'B', 'Q', 'K', 'B', 'N', 'R']
    ]
    
    # Reset game state
    selected_square = None
    current_turn = 'white'
    move_history = []
    valid_moves = []
    game_over = False
    game_result = ""
    
    # Reset special moves
    piece_moved = {
        'white_king': False,
        'white_rook_a': False,
        'white_rook_h': False,
        'black_king': False,
        'black_rook_a': False,
        'black_rook_h': False,
    }
    en_passant_target = None
    promotion_pending = None
    
    # Reset captured pieces
    captured_pieces = {'white': [], 'black': []}
    
    # Reset animation
    animating_move = None
    
    # Reset evaluation
    evaluation_history = []
    current_evaluation = 0
    
    # Reset check cache
    white_in_check_cached = False
    black_in_check_cached = False
    
    # Reset history/replay
    board_history = []
    game_state_history = []
    current_move_index = -1
    
    # Reset draw conditions
    position_history = {}
    halfmove_clock = 0
    
    # Reset AI tables
    transposition_table = {}
    pv_table = {}
    history_score = {}
    killer_moves = {}
    
    # Reset time controls
    if time_control:
        white_time_remaining = time_control['time']
        black_time_remaining = time_control['time']
        last_time_update = None
        time_exceeded = None
    
    # Reinitialize zobrist if you're using it
    try:
        init_current_zobrist()
    except:
        pass
    
    print("NEW GAME STARTED")
    print("Current turn: White")
    print("="*50 + "\n")
#===========================================================================TERMINAL BOARD===========================================================================
print("GAME STARTED")
for row in board:
    print(row)
# Initialize Zobrist table and record initial position for repetition tracking
init_zobrist(seed=0)
init_current_zobrist()
initial_key = get_position_key()
position_history[initial_key] = position_history.get(initial_key, 0) + 1
#===========================================================================GAME MODE SELECTION===========================================================================
def select_game_mode():
    """Display game mode selection screen"""
    global game_mode
    
    clock_local = pygame.time.Clock()
    mode_selected = False
    
    # Button dimensions
    button_width = 300
    button_height = 80
    button_y_offset = 80
    
    # AI button
    ai_button_rect = pygame.Rect(width // 2 - button_width // 2, height // 2 - button_height // 2 - button_y_offset, button_width, button_height)
    # Two Player button
    two_player_button_rect = pygame.Rect(width // 2 - button_width // 2, height // 2 - button_height // 2 + button_y_offset, button_width, button_height)
    
    hover_ai = False
    hover_two = False
    
    while not mode_selected:
        clock_local.tick(60)
        mouse_pos = pygame.mouse.get_pos()
        
        # Check hover states
        hover_ai = ai_button_rect.collidepoint(mouse_pos)
        hover_two = two_player_button_rect.collidepoint(mouse_pos)
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            
            if event.type == pygame.MOUSEBUTTONDOWN:
                if hover_ai:
                    game_mode = 'ai'
                    mode_selected = True
                elif hover_two:
                    game_mode = 'two_player'
                    mode_selected = True
        
        # Draw background
        screen.fill((30, 30, 40))
        
        # Draw title
        title = "CHESS GAME"
        title_surface = large_font.render(title, True, (255, 215, 0))
        title_shadow = large_font.render(title, True, (0, 0, 0))
        title_rect = title_surface.get_rect(center=(width // 2, height // 4))
        title_shadow_rect = title_shadow.get_rect(center=(width // 2 + 3, height // 4 + 3))
        screen.blit(title_shadow, title_shadow_rect)
        screen.blit(title_surface, title_rect)
        
        # Draw subtitle
        subtitle = "Select Game Mode"
        subtitle_surface = small_font.render(subtitle, True, (200, 200, 200))
        subtitle_rect = subtitle_surface.get_rect(center=(width // 2, height // 4 + 70))
        screen.blit(subtitle_surface, subtitle_rect)
        
        # Draw AI button
        ai_color = (100, 150, 200) if hover_ai else (70, 100, 150)
        ai_border = (200, 200, 255) if hover_ai else (150, 150, 200)
        pygame.draw.rect(screen, ai_color, ai_button_rect)
        pygame.draw.rect(screen, ai_border, ai_button_rect, 3)
        
        ai_text = "Play vs AI"
        ai_text_surface = font.render(ai_text, True, White)
        ai_text_rect = ai_text_surface.get_rect(center=ai_button_rect.center)
        screen.blit(ai_text_surface, ai_text_rect)
        
        if hover_ai:
            ai_desc = "Challenge the computer"
            ai_desc_surface = tiny_font.render(ai_desc, True, (200, 200, 200))
            ai_desc_rect = ai_desc_surface.get_rect(center=(ai_button_rect.centerx, ai_button_rect.bottom + 25))
            screen.blit(ai_desc_surface, ai_desc_rect)
        
        # Draw Two Player button
        two_color = (150, 100, 200) if hover_two else (100, 70, 150)
        two_border = (200, 150, 255) if hover_two else (150, 100, 200)
        pygame.draw.rect(screen, two_color, two_player_button_rect)
        pygame.draw.rect(screen, two_border, two_player_button_rect, 3)
        
        two_text = "Two Player"
        two_text_surface = font.render(two_text, True, White)
        two_text_rect = two_text_surface.get_rect(center=two_player_button_rect.center)
        screen.blit(two_text_surface, two_text_rect)
        
        if hover_two:
            two_desc = "Play with a friend"
            two_desc_surface = tiny_font.render(two_desc, True, (200, 200, 200))
            two_desc_rect = two_desc_surface.get_rect(center=(two_player_button_rect.centerx, two_player_button_rect.bottom + 25))
            screen.blit(two_desc_surface, two_desc_rect)
        
        pygame.display.flip()

def select_time_control():
    global time_control, white_time_remaining, black_time_remaining, last_time_update
    
    clock_local = pygame.time.Clock()
    control_selected = False
    
    button_width = 220
    button_height = 70
    button_spacing = 90
    
    no_clock_rect = pygame.Rect(width // 2 - button_width // 2, height // 2 - button_height // 2 - button_spacing, button_width, button_height)
    five_min_rect = pygame.Rect(width // 2 - button_width // 2, height // 2 - button_height // 2, button_width, button_height)
    ten_min_rect = pygame.Rect(width // 2 - button_width // 2, height // 2 - button_height // 2 + button_spacing, button_width, button_height)
    
    hover_no_clock = False
    hover_five = False
    hover_ten = False
    
    while not control_selected:
        clock_local.tick(60)
        mouse_pos = pygame.mouse.get_pos()
        
        hover_no_clock = no_clock_rect.collidepoint(mouse_pos)
        hover_five = five_min_rect.collidepoint(mouse_pos)
        hover_ten = ten_min_rect.collidepoint(mouse_pos)
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            
            if event.type == pygame.MOUSEBUTTONDOWN:
                if hover_no_clock:
                    time_control = 'no_clock'
                    control_selected = True
                elif hover_five:
                    time_control = '5min'
                    white_time_remaining = 300
                    black_time_remaining = 300
                    control_selected = True
                elif hover_ten:
                    time_control = '10min'
                    white_time_remaining = 600
                    black_time_remaining = 600
                    control_selected = True
        
        screen.fill((30, 30, 40))
        
        title = "Time Control"
        title_surface = large_font.render(title, True, (255, 215, 0))
        title_shadow = large_font.render(title, True, (0, 0, 0))
        title_rect = title_surface.get_rect(center=(width // 2, height // 4))
        title_shadow_rect = title_shadow.get_rect(center=(width // 2 + 3, height // 4 + 3))
        screen.blit(title_shadow, title_shadow_rect)
        screen.blit(title_surface, title_rect)
        
        subtitle = "Select Time Limit"
        subtitle_surface = small_font.render(subtitle, True, (200, 200, 200))
        subtitle_rect = subtitle_surface.get_rect(center=(width // 2, height // 4 + 70))
        screen.blit(subtitle_surface, subtitle_rect)
        
        no_color = (100, 180, 100) if hover_no_clock else (70, 130, 70)
        no_border = (150, 255, 150) if hover_no_clock else (100, 200, 100)
        pygame.draw.rect(screen, no_color, no_clock_rect)
        pygame.draw.rect(screen, no_border, no_clock_rect, 3)
        
        no_text = "No Clock"
        no_text_surface = font.render(no_text, True, White)
        no_text_rect = no_text_surface.get_rect(center=no_clock_rect.center)
        screen.blit(no_text_surface, no_text_rect)
        
        if hover_no_clock:
            no_desc = "Unlimited time"
            no_desc_surface = tiny_font.render(no_desc, True, (200, 200, 200))
            no_desc_rect = no_desc_surface.get_rect(center=(no_clock_rect.centerx, no_clock_rect.bottom + 15))
            screen.blit(no_desc_surface, no_desc_rect)
        
        five_color = (100, 150, 200) if hover_five else (70, 100, 150)
        five_border = (200, 200, 255) if hover_five else (150, 150, 200)
        pygame.draw.rect(screen, five_color, five_min_rect)
        pygame.draw.rect(screen, five_border, five_min_rect, 3)
        
        five_text = "5 Minutes"
        five_text_surface = font.render(five_text, True, White)
        five_text_rect = five_text_surface.get_rect(center=five_min_rect.center)
        screen.blit(five_text_surface, five_text_rect)
        
        if hover_five:
            five_desc = "5 min per player"
            five_desc_surface = tiny_font.render(five_desc, True, (200, 200, 200))
            five_desc_rect = five_desc_surface.get_rect(center=(five_min_rect.centerx, five_min_rect.bottom + 15))
            screen.blit(five_desc_surface, five_desc_rect)
        
        ten_color = (200, 100, 150) if hover_ten else (150, 70, 100)
        ten_border = (255, 150, 200) if hover_ten else (200, 100, 150)
        pygame.draw.rect(screen, ten_color, ten_min_rect)
        pygame.draw.rect(screen, ten_border, ten_min_rect, 3)
        
        ten_text = "10 Minutes"
        ten_text_surface = font.render(ten_text, True, White)
        ten_text_rect = ten_text_surface.get_rect(center=ten_min_rect.center)
        screen.blit(ten_text_surface, ten_text_rect)
        
        if hover_ten:
            ten_desc = "10 min per player"
            ten_desc_surface = tiny_font.render(ten_desc, True, (200, 200, 200))
            ten_desc_rect = ten_desc_surface.get_rect(center=(ten_min_rect.centerx, ten_min_rect.bottom + 15))
            screen.blit(ten_desc_surface, ten_desc_rect)
        
        pygame.display.flip()
#===========================================================================TERMINAL BOARD===========================================================================
print("GAME STARTED")
for row in board:
    print(row)
#===========================================================================MAIN GAME LOOP===========================================================================
# First, show game mode selection
select_game_mode()
print(f"Game mode selected: {game_mode}")
# If two-player mode, show time control selection
if game_mode == 'two_player':
    select_time_control()
    print(f"Time control selected: {time_control}")
"""===========================================================================SETUP==========================================================================="""
run = True
clock = pygame.time.Clock()
images_loaded = load_images()
sounds_loaded = load_sounds()
# Initialize check cache
white_in_check_cached = is_in_check('white')
black_in_check_cached = is_in_check('black')
#===========================================================================GAME LOOP===========================================================================
while run:
    
    # Update hover effect
    if pygame.mouse.get_focused():
        mouse_pos = pygame.mouse.get_pos()
        if mouse_pos[0] < board_width:
            hover_square = get_square_from_mouse(mouse_pos)
        else:
            hover_square = None
    
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            run = False
            continue
        
        # Handle keyboard navigation for replay (arrow keys)
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_LEFT:  # Left arrow - previous move
                if current_move_index > -1:
                    jump_to_move(current_move_index - 1)
                    selected_square = None
                    valid_moves = []
            elif event.key == pygame.K_RIGHT:  # Right arrow - next move
                if current_move_index < len(move_history) - 1:
                    jump_to_move(current_move_index + 1)
                    selected_square = None
                    valid_moves = []
            elif event.key == pygame.K_END:  # End key - go to live game
                jump_to_move(-1)
                selected_square = None
                valid_moves = []
            elif event.key == pygame.K_HOME:  # Home key - go to start
                jump_to_move(0)
                selected_square = None
                valid_moves = []
        
        if promotion_pending:
            if event.type == pygame.QUIT:
                run = False
                continue
            if event.type == pygame.MOUSEBUTTONDOWN:
                x, y = event.pos
                for i, p in enumerate(['Q', 'R', 'B', 'N']):
                    button_x = 100 + i * 160
                    button_rect = pygame.Rect(button_x, height // 2 - 20, 120, 120)
                    if button_rect.collidepoint(x, y):
                        row, col = promotion_pending
                        promote_pawn(row, col, p)
                        play_sound('promote', volume=0.6)
                        promotion_pending = None
                        switch_turn()
                        break
            continue

        if event.type == pygame.MOUSEBUTTONDOWN:

            if new_game_button_rect and new_game_button_rect.collidepoint(event.pos):
                reset_game()
                continue

            if game_over:
                run = False
                continue

            mouse_pos = event.pos
            
            # Check for replay button clicks
            button_clicked = False
            for button_name, rect in replay_button_rects.items():
                if rect.collidepoint(mouse_pos):
                    if button_name == 'prev' and current_move_index > -1:
                        jump_to_move(current_move_index - 1)
                        button_clicked = True
                    elif button_name == 'next' and current_move_index < len(move_history) - 1:
                        jump_to_move(current_move_index + 1)
                        button_clicked = True
                    elif button_name == 'live':
                        jump_to_move(-1)
                        button_clicked = True
                    selected_square = None
                    valid_moves = []
                    break
            
            if button_clicked:
                continue
            
            # Check for move history clicks (replay feature)
            for move_idx, rect in move_history_rects.items():
                if rect.collidepoint(mouse_pos):
                    jump_to_move(move_idx)
                    selected_square = None
                    valid_moves = []
                    button_clicked = True
                    break
            
            if button_clicked:
                continue

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
        # Update clocks in 2-player mode
        if game_mode == 'two_player':
            update_clocks()
        
        
        # AI's turn - only in AI mode and only after animation completes
        if game_mode == 'ai' and current_turn == 'black' and not animating_move:
            ai_is_thinking = True
            play_sound('ai_thinking', volume=0.2)
            draw_board()
            draw_pieces()
            draw_right_panel()
            draw_ai_thinking_overlay()
            pygame.display.flip()
            move = get_best_move_minimax('black')
            ai_is_thinking = False
            if move:
                from_square, to_square = move
                move_piece(from_square, to_square)
                if not promotion_pending:
                    switch_turn()

    draw_board()
    draw_pieces()
    new_game_button_rect = draw_right_panel()
    if game_mode == 'two_player':
        draw_clocks()
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
