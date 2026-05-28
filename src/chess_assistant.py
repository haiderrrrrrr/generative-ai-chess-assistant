#!/usr/bin/env python3
import sys
import copy
import math
import os
import random
import time
from typing import List, Tuple, Optional, Dict

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

#######################################################
# PART 1: CONSTANTS, ANSI CODES, BASIC BOARD SETUP
#######################################################

RESET = "\033[0m"

# Background colors for board squares:
LIGHT_SQ_BG = "\033[48;5;229m"  # a light shade
DARK_SQ_BG  = "\033[48;5;179m"  # a darker shade
HIGHLIGHT_BG = "\033[48;5;214m"
WHITE_PIECE_COLOR = "\033[1;37m"  # bright white
BLACK_PIECE_COLOR = "\033[1;30m"  # gray/black
WARNING_COLOR = "\033[1;31m"     # bold red

def color_square(r: int, c: int) -> str:
    """Return the background color escape code for the board square at row r, col c."""
    if (r + c) % 2 == 0:
        return LIGHT_SQ_BG
    else:
        return DARK_SQ_BG

# Piece Unicode Map
UNICODE_PIECES = {
    'K': '♔', 'Q': '♕', 'R': '♖', 'B': '♗', 'N': '♘', 'P': '♙',
    'k': '♚', 'q': '♛', 'r': '♜', 'b': '♝', 'n': '♞', 'p': '♟',
    '.': '  '
}

# Basic piece values for AI evaluation (material)
PIECE_VALUES = {
    'K': 10000,
    'Q': 900,
    'R': 500,
    'B': 330,
    'N': 320,
    'P': 100
}

def piece_value(piece: str) -> int:
    """Return the 'material value' of the piece (for evaluation)."""
    if piece == '.':
        return 0
    return PIECE_VALUES.get(piece.upper(), 0)

def is_white(piece: str) -> bool:
    return piece.isupper()

def is_black(piece: str) -> bool:
    return piece.islower()

def opposite_color(a: str, b: str) -> bool:
    """True if piece a and piece b are of opposite colors."""
    if a == '.' or b == '.':
        return False
    return (a.isupper() and b.islower()) or (a.islower() and b.isupper())

def same_color(a: str, b: str) -> bool:
    """True if piece a and piece b are of the same color."""
    if a == '.' or b == '.':
        return False
    return (a.isupper() and b.isupper()) or (a.islower() and b.islower())

def in_bounds(r: int, c: int) -> bool:
    return 0 <= r < 8 and 0 <= c < 8

def starting_board() -> List[List[str]]:
    """Return an 8x8 matrix with standard chess initial position."""
    ranks = [
        list("rnbqkbnr"),
        list("pppppppp"),
        list("........"),
        list("........"),
        list("........"),
        list("........"),
        list("PPPPPPPP"),
        list("RNBQKBNR")
    ]
    return ranks

#######################################################
# PART 2: FEN SAVE/LOAD, MOVE CLASS, MAKE/UNDO
#######################################################

def board_to_fen(board: List[List[str]], side_to_move: str, castling_rights: str,
                 en_passant_square: str, halfmove_clock: int, fullmove_number: int) -> str:
    """
    Generate a simplified FEN string from the board and state.
    """
    fen_rows = []
    for row in board:
        empty_count = 0
        fen_row = ""
        for piece in row:
            if piece == '.':
                empty_count += 1
            else:
                if empty_count > 0:
                    fen_row += str(empty_count)
                    empty_count = 0
                fen_row += piece
        if empty_count > 0:
            fen_row += str(empty_count)
        fen_rows.append(fen_row)
    piece_placement = "/".join(fen_rows)
    if castling_rights == "":
        castling_rights = "-"
    if en_passant_square == "":
        en_passant_square = "-"
    fen_str = f"{piece_placement} {side_to_move} {castling_rights} {en_passant_square} {halfmove_clock} {fullmove_number}"
    return fen_str

def fen_to_board(fen: str) -> Tuple[List[List[str]], str, str, str, int, int]:
    """
    Parse a FEN string into (board, side_to_move, castling_rights, en_passant, halfmove, fullmove).
    """
    parts = fen.split()
    piece_placement = parts[0]
    side_to_move = parts[1]
    castling_rights = parts[2]
    en_passant_square = parts[3]
    halfmove_clock = int(parts[4])
    fullmove_number = int(parts[5])

    rows = piece_placement.split('/')
    board = []
    for r in rows:
        row = []
        for ch in r:
            if ch.isdigit():
                count = int(ch)
                row.extend(['.'] * count)
            else:
                row.append(ch)
        board.append(row)
    return board, side_to_move, castling_rights, en_passant_square, halfmove_clock, fullmove_number

class Move:
    def __init__(self, r1, c1, r2, c2, piece, captured='.',
                 promotion=None, is_castling=False, is_en_passant=False):
        self.r1 = r1
        self.c1 = c1
        self.r2 = r2
        self.c2 = c2
        self.piece = piece       # The piece that moved
        self.captured = captured # The piece captured, if any
        self.promotion = promotion
        self.is_castling = is_castling
        self.is_en_passant = is_en_passant

    def __repr__(self):
        return (f"Move({self.r1},{self.c1} -> {self.r2},{self.c2}, "
                f"piece={self.piece}, cap={self.captured}, "
                f"prom={self.promotion}, castl={self.is_castling}, ep={self.is_en_passant})")

def algebraic_notation(move: 'Move') -> str:
    """Simple algebraic notation, e.g., e2e4 or e7e8=Q."""
    fr_file = chr(move.c1 + ord('a'))
    fr_rank = str(8 - move.r1)
    to_file = chr(move.c2 + ord('a'))
    to_rank = str(8 - move.r2)
    s = f"{fr_file}{fr_rank}{to_file}{to_rank}"
    if move.promotion:
        s += f"={move.promotion.upper()}"
    return s

def make_move(board: List[List[str]], move: 'Move') -> None:
    """Execute a move on the board in-place."""
    if move.is_castling:
        # Move the king
        board[move.r2][move.c2] = move.piece
        board[move.r1][move.c1] = '.'
        # Move the rook
        if move.c2 == 6:  # kingside
            board[move.r2][5] = board[move.r2][7]
            board[move.r2][7] = '.'
        else:             # queenside
            board[move.r2][3] = board[move.r2][0]
            board[move.r2][0] = '.'
        return

    if move.is_en_passant:
        board[move.r2][move.c2] = move.piece
        board[move.r1][move.c1] = '.'
        # remove the captured pawn
        direction = -1 if is_white(move.piece) else 1
        board[move.r2 + direction][move.c2] = '.'
        return

    # Normal or promotion
    board[move.r2][move.c2] = move.piece if not move.promotion else move.promotion
    board[move.r1][move.c1] = '.'

def undo_move(board: List[List[str]], move: 'Move') -> None:
    """Revert a move on the board (in-place)."""
    if move.is_castling:
        board[move.r1][move.c1] = move.piece
        board[move.r2][move.c2] = '.'
        if move.c2 == 6:  # kingside
            board[move.r2][7] = board[move.r2][5]
            board[move.r2][5] = '.'
        else:
            board[move.r2][0] = board[move.r2][3]
            board[move.r2][3] = '.'
        return

    if move.is_en_passant:
        board[move.r1][move.c1] = move.piece
        board[move.r2][move.c2] = '.'
        direction = -1 if is_white(move.piece) else 1
        board[move.r2 + direction][move.c2] = move.captured
        return

    board[move.r1][move.c1] = move.piece
    board[move.r2][move.c2] = move.captured

#######################################################
# PART 3: MOVE GENERATION, VALIDATION, CHECK/CASTLING
#######################################################

def generate_moves(board: List[List[str]], side_to_move: str,
                   castling_rights: str, en_passant_square: str) -> List[Move]:
    """Generate all pseudo-legal moves for side_to_move, ignoring check safety."""
    moves = []
    ep_r, ep_c = None, None
    if en_passant_square not in ['-', '']:
        ffile = ord(en_passant_square[0]) - ord('a')
        frank = 8 - int(en_passant_square[1])
        ep_r, ep_c = frank, ffile

    def correct_color(piece: str):
        if side_to_move == 'w':
            return is_white(piece)
        else:
            return is_black(piece)

    for r in range(8):
        for c in range(8):
            piece = board[r][c]
            if piece == '.' or not correct_color(piece):
                continue
            pmoves = generate_moves_for_piece(board, r, c, piece,
                                              castling_rights, side_to_move,
                                              (ep_r, ep_c))
            moves.extend(pmoves)
    return moves

def generate_moves_for_piece(board, r, c, piece, castling_rights,
                             side_to_move, en_passant_coords) -> List[Move]:
    moves = []
    color = 'w' if is_white(piece) else 'b'
    direction = -1 if color == 'w' else 1
    ep_r, ep_c = en_passant_coords
    piece_upper = piece.upper()

    if piece_upper == 'P':
        # Pawns
        fr = r + direction
        if in_bounds(fr, c) and board[fr][c] == '.':
            prom = check_pawn_promotion(r, c, fr, c, piece)
            moves.append(Move(r, c, fr, c, piece, promotion=prom))
            # Double step if on starting rank
            starting_rank = 6 if color == 'w' else 1
            if r == starting_rank:
                fr2 = r + 2*direction
                if board[fr2][c] == '.':
                    moves.append(Move(r, c, fr2, c, piece))

        # Captures
        for cc in [c-1, c+1]:
            rr = r + direction
            if in_bounds(rr, cc):
                target = board[rr][cc]
                if target != '.' and opposite_color(piece, target):
                    prom = check_pawn_promotion(r, c, rr, cc, piece)
                    moves.append(Move(r, c, rr, cc, piece, captured=target, promotion=prom))

        # En passant
        if ep_r is not None and ep_c is not None:
            if (r + direction == ep_r) and (abs(c - ep_c) == 1):
                cap = 'P' if color=='b' else 'p'
                moves.append(Move(r, c, ep_r, ep_c, piece, captured=cap, is_en_passant=True))

    elif piece_upper == 'N':
        offsets = [(2,1),(2,-1),(-2,1),(-2,-1),(1,2),(1,-2),(-1,2),(-1,-2)]
        for (dr,dc) in offsets:
            rr, cc = r+dr, c+dc
            if in_bounds(rr, cc):
                target = board[rr][cc]
                if target=='.' or opposite_color(piece,target):
                    moves.append(Move(r,c,rr,cc,piece,captured=target))

    elif piece_upper == 'B':
        directions = [(-1,-1),(-1,1),(1,-1),(1,1)]
        for (dr,dc) in directions:
            rr, cc = r+dr, c+dc
            while in_bounds(rr, cc):
                target = board[rr][cc]
                if target == '.':
                    moves.append(Move(r,c,rr,cc,piece))
                else:
                    if opposite_color(piece,target):
                        moves.append(Move(r,c,rr,cc,piece,captured=target))
                    break
                rr += dr
                cc += dc

    elif piece_upper == 'R':
        directions = [(-1,0),(1,0),(0,-1),(0,1)]
        for (dr,dc) in directions:
            rr, cc = r+dr, c+dc
            while in_bounds(rr, cc):
                target = board[rr][cc]
                if target == '.':
                    moves.append(Move(r,c,rr,cc,piece))
                else:
                    if opposite_color(piece,target):
                        moves.append(Move(r,c,rr,cc,piece,captured=target))
                    break
                rr += dr
                cc += dc

    elif piece_upper == 'Q':
        directions = [(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(-1,1),(1,-1),(1,1)]
        for (dr,dc) in directions:
            rr, cc = r+dr, c+dc
            while in_bounds(rr, cc):
                target = board[rr][cc]
                if target == '.':
                    moves.append(Move(r,c,rr,cc,piece))
                else:
                    if opposite_color(piece,target):
                        moves.append(Move(r,c,rr,cc,piece,captured=target))
                    break
                rr += dr
                cc += dc

    elif piece_upper == 'K':
        king_moves = [(r+dr, c+dc) for dr in [-1,0,1] for dc in [-1,0,1] if not(dr==0 and dc==0)]
        for (rr,cc) in king_moves:
            if in_bounds(rr, cc):
                target = board[rr][cc]
                if target=='.' or opposite_color(piece,target):
                    moves.append(Move(r,c,rr,cc,piece,captured=target))
        # Castling
        if color=='w' and r==7 and c==4:
            if 'K' in castling_rights:
                if board[7][5]=='.' and board[7][6]=='.':
                    moves.append(Move(r,c,7,6,piece,is_castling=True))
            if 'Q' in castling_rights:
                if board[7][3]=='.' and board[7][2]=='.' and board[7][1]=='.':
                    moves.append(Move(r,c,7,2,piece,is_castling=True))
        elif color=='b' and r==0 and c==4:
            if 'k' in castling_rights:
                if board[0][5]=='.' and board[0][6]=='.':
                    moves.append(Move(r,c,0,6,piece,is_castling=True))
            if 'q' in castling_rights:
                if board[0][3]=='.' and board[0][2]=='.' and board[0][1]=='.':
                    moves.append(Move(r,c,0,2,piece,is_castling=True))

    return moves

def check_pawn_promotion(r1, c1, r2, c2, piece) -> Optional[str]:
    """Return promoted piece char if the pawn is moving to last rank, else None."""
    if is_white(piece) and r2 == 0:
        return 'Q'
    if is_black(piece) and r2 == 7:
        return 'q'
    return None

def filter_legal_moves(board: List[List[str]], moves: List[Move], side_to_move: str,
                       castling_rights: str, en_passant_square: str) -> List[Move]:
    """Return only moves that don't leave own king in check."""
    legal = []
    for mv in moves:
        make_move(board, mv)
        if not king_in_check(board, side_to_move):
            legal.append(mv)
        undo_move(board, mv)
    return legal

def king_in_check(board: List[List[str]], side: str) -> bool:
    """True if side's king is in check."""
    king_char = 'K' if side=='w' else 'k'
    king_pos = None
    for r in range(8):
        for c in range(8):
            if board[r][c] == king_char:
                king_pos = (r,c)
                break
        if king_pos is not None:
            break
    if not king_pos:
        # No king found - treat as 'check' for safety
        return True
    enemy_side = 'b' if side=='w' else 'w'
    enemy_moves = generate_moves(board, enemy_side, "", '-')
    for mv in enemy_moves:
        if (mv.r2, mv.c2) == king_pos:
            return True
    return False

def is_checkmate(board: List[List[str]], side: str,
                 castling_rights: str, en_passant_square: str) -> bool:
    if not king_in_check(board, side):
        return False
    moves_all = generate_moves(board, side, castling_rights, en_passant_square)
    moves_legal = filter_legal_moves(board, moves_all, side, castling_rights, en_passant_square)
    return len(moves_legal) == 0

def is_stalemate(board: List[List[str]], side: str,
                 castling_rights: str, en_passant_square: str) -> bool:
    if king_in_check(board, side):
        return False
    moves_all = generate_moves(board, side, castling_rights, en_passant_square)
    moves_legal = filter_legal_moves(board, moves_all, side, castling_rights, en_passant_square)
    return len(moves_legal) == 0

def update_castling_rights(castling_rights: str, move: Move, board: List[List[str]]) -> str:
    cr = castling_rights
    piece = move.piece
    # If king moves, lose both sides
    if piece == 'K':
        cr = cr.replace('K','').replace('Q','')
    elif piece == 'k':
        cr = cr.replace('k','').replace('q','')
    # If rook moves or is captured, remove that side
    elif piece == 'R':
        if move.r1==7 and move.c1==7:
            cr = cr.replace('K','')
        elif move.r1==7 and move.c1==0:
            cr = cr.replace('Q','')
    elif piece == 'r':
        if move.r1==0 and move.c1==7:
            cr = cr.replace('k','')
        elif move.r1==0 and move.c1==0:
            cr = cr.replace('q','')

    if move.captured == 'R':
        if move.r2==7 and move.c2==7:
            cr = cr.replace('K','')
        elif move.r2==7 and move.c2==0:
            cr = cr.replace('Q','')
    elif move.captured == 'r':
        if move.r2==0 and move.c2==7:
            cr = cr.replace('k','')
        elif move.r2==0 and move.c2==0:
            cr = cr.replace('q','')

    return cr

def update_en_passant_square(move: Move, board: List[List[str]]) -> str:
    """If a pawn moved two squares, set the en_passant square. Otherwise '-'."""
    if move.piece.upper() == 'P':
        if abs(move.r2 - move.r1) == 2:
            row = (move.r1 + move.r2)//2
            col = move.c1
            file = chr(col + ord('a'))
            rank = str(8 - row)
            return file+rank
    return '-'

#######################################################
# PART 4: ADVANCED EVALUATION + ITERATIVE DEEPENING
#######################################################

# Basic piece-square table example for improved positional scoring
# Format: PST[Piece][row][col]
# We'll define for White; for Black we invert indices.

PST_PAWN = [
    [  0,   0,   0,   0,   0,   0,   0,   0],
    [ 50,  50,  50,  50,  50,  50,  50,  50],
    [ 10,  10,  20,  30,  30,  20,  10,  10],
    [  5,   5,  10,  25,  25,  10,   5,   5],
    [  0,   0,   0,  20,  20,   0,   0,   0],
    [  5,  -5, -10,   0,   0, -10,  -5,   5],
    [  5,  10,  10, -20, -20,  10,  10,   5],
    [  0,   0,   0,   0,   0,   0,   0,   0]
]

PST_KNIGHT = [
    [-50, -40, -30, -30, -30, -30, -40, -50],
    [-40, -20,   0,   5,   5,   0, -20, -40],
    [-30,   5,  10,  15,  15,  10,   5, -30],
    [-30,   0,  15,  20,  20,  15,   0, -30],
    [-30,   5,  15,  20,  20,  15,   5, -30],
    [-30,   0,  10,  15,  15,  10,   0, -30],
    [-40, -20,   0,   0,   0,   0, -20, -40],
    [-50, -40, -30, -30, -30, -30, -40, -50]
]

PST_BISHOP = [
    [-20, -10, -10, -10, -10, -10, -10, -20],
    [-10,   0,   0,   5,   5,   0,   0, -10],
    [-10,  10,  10,  10,  10,  10,  10, -10],
    [-10,   5,  10,  10,  10,  10,   5, -10],
    [-10,   0,  10,  10,  10,  10,   0, -10],
    [-10,   5,   5,  10,  10,   5,   5, -10],
    [-10,   0,   0,   0,   0,   0,   0, -10],
    [-20, -10, -10, -10, -10, -10, -10, -20]
]

PST_ROOK = [
    [  0,   0,   0,   0,   0,   0,   0,   0],
    [  5,  10,  10,  10,  10,  10,  10,   5],
    [ -5,   0,   0,   0,   0,   0,   0,  -5],
    [ -5,   0,   0,   0,   0,   0,   0,  -5],
    [ -5,   0,   0,   0,   0,   0,   0,  -5],
    [ -5,   0,   0,   0,   0,   0,   0,  -5],
    [  5,  10,  10,  10,  10,  10,  10,   5],
    [  0,   0,   0,   5,   5,   0,   0,   0]
]

PST_QUEEN = [
    [-20, -10, -10,  -5,  -5, -10, -10, -20],
    [-10,   0,   0,   0,   0,   0,   0, -10],
    [-10,   0,   5,   5,   5,   5,   0, -10],
    [ -5,   0,   5,   5,   5,   5,   0,  -5],
    [  0,   0,   5,   5,   5,   5,   0,  -5],
    [-10,   5,   5,   5,   5,   5,   0, -10],
    [-10,   0,   5,   0,   0,   0,   0, -10],
    [-20, -10, -10,  -5,  -5, -10, -10, -20]
]

PST_KING = [
    [ 20,  30,  10,   0,   0,  10,  30,  20],
    [ 20,  20,   0,   0,   0,   0,  20,  20],
    [-10, -20, -20, -20, -20, -20, -20, -10],
    [-20, -30, -30, -40, -40, -30, -30, -20],
    [-30, -40, -40, -50, -50, -40, -40, -30],
    [-30, -40, -40, -50, -50, -40, -40, -30],
    [-30, -40, -40, -50, -50, -40, -40, -30],
    [-30, -40, -40, -50, -50, -40, -40, -30]
]

# We'll keep a dictionary mapping piece -> PST for White;
# For Black, we invert row index
PIECE_SQUARE_TABLES = {
    'P': PST_PAWN,
    'N': PST_KNIGHT,
    'B': PST_BISHOP,
    'R': PST_ROOK,
    'Q': PST_QUEEN,
    'K': PST_KING
}

def pst_score(piece: str, r: int, c: int) -> int:
    """Return piece-square table bonus for piece at row, col."""
    # For White, row is as is. For Black, we flip row to get mirror
    # (eg. black's row0 is like white's row7).
    if piece == '.':
        return 0
    table = PIECE_SQUARE_TABLES.get(piece.upper(), None)
    if not table:
        return 0
    row = r if is_white(piece) else 7-r
    col = c
    sign = 1 if is_white(piece) else -1
    return sign * table[row][col]

def evaluate_position(board: List[List[str]]) -> int:
    """
    More advanced evaluation: material + piece-square table.
    Positive => White is better, negative => Black is better.
    """
    score = 0
    for r in range(8):
        for c in range(8):
            piece = board[r][c]
            if piece == '.':
                continue
            val = piece_value(piece)  # material
            # PST bonus
            val += pst_score(piece, r, c)
            if is_white(piece):
                score += val
            else:
                score -= val
    return score

#
#  We'll add some advanced or iterative deepening approach with TT
#
TRANSPOSITION_TABLE: Dict[int, Tuple[int,int,int]] = {}  # hash -> (score, depth, flag)
EXACT, ALPHA, BETA = 0, 1, 2

def compute_zobrist_hash(board: List[List[str]], side: str,
                         castling: str, en_passant: str,
                         halfmove_clock: int, fullmove_number: int) -> int:
    """
    For demonstration, an extremely simplistic "hash."
    Real Zobrist hashing uses random bitstrings per piece-square.
    We'll do a naive approach for brevity.
    """
    # It's not truly robust, but enough for demonstration.
    hval = 0
    for r in range(8):
        for c in range(8):
            piece = board[r][c]
            hval ^= hash((r, c, piece))
    hval ^= hash(side)
    hval ^= hash(castling)
    hval ^= hash(en_passant)
    return hval

def alpha_beta_tt(board: List[List[str]], depth: int, alpha: int, beta: int,
                  maximizing: bool, side: str, castling: str,
                  en_passant: str, halfmove: int, fullmove: int) -> int:
    """
    Alpha-beta search with transposition table and piece-square evaluation.
    """
    # Terminal checks
    if depth == 0:
        return evaluate_position(board)

    if is_checkmate(board, side, castling, en_passant):
        return -99999 if maximizing else 99999
    if is_stalemate(board, side, castling, en_passant):
        return 0

    # hashing
    key = compute_zobrist_hash(board, side, castling, en_passant, halfmove, fullmove)
    if key in TRANSPOSITION_TABLE:
        (stored_score, stored_depth, stored_flag) = TRANSPOSITION_TABLE[key]
        if stored_depth >= depth:
            if stored_flag == EXACT:
                return stored_score
            elif stored_flag == ALPHA and stored_score <= alpha:
                return alpha
            elif stored_flag == BETA and stored_score >= beta:
                return beta

    moves_all = generate_moves(board, side, castling, en_passant)
    moves_legal = filter_legal_moves(board, moves_all, side, castling, en_passant)
    if not moves_legal:
        return evaluate_position(board)

    next_side = 'b' if side=='w' else 'w'
    if maximizing:
        best_val = -math.inf
        for mv in moves_legal:
            saved_castling = castling
            saved_enp = en_passant
            make_move(board, mv)
            new_cr = update_castling_rights(saved_castling, mv, board)
            new_ep = update_en_passant_square(mv, board)
            val = alpha_beta_tt(board, depth-1, alpha, beta, False,
                                next_side, new_cr, new_ep, halfmove, fullmove)
            undo_move(board, mv)
            castling = saved_castling
            en_passant = saved_enp

            best_val = max(best_val, val)
            alpha = max(alpha, val)
            if alpha >= beta:
                break

        # store TT
        store_tt(key, best_val, depth, alpha, beta)
        return best_val
    else:
        best_val = math.inf
        for mv in moves_legal:
            saved_castling = castling
            saved_enp = en_passant
            make_move(board, mv)
            new_cr = update_castling_rights(saved_castling, mv, board)
            new_ep = update_en_passant_square(mv, board)
            val = alpha_beta_tt(board, depth-1, alpha, beta, True,
                                next_side, new_cr, new_ep, halfmove, fullmove)
            undo_move(board, mv)
            castling = saved_castling
            en_passant = saved_enp

            best_val = min(best_val, val)
            beta = min(beta, val)
            if alpha >= beta:
                break

        store_tt(key, best_val, depth, alpha, beta)
        return best_val

def store_tt(key: int, score: int, depth: int, alpha: int, beta: int):
    # EXACT, ALPHA, or BETA
    flag = EXACT
    if score <= alpha:
        flag = BETA
    elif score >= beta:
        flag = ALPHA
    TRANSPOSITION_TABLE[key] = (score, depth, flag)

def iterative_deepening_search(board: List[List[str]], side: str,
                               castling: str, en_passant: str,
                               halfmove: int, fullmove: int,
                               max_depth: int = 4,
                               time_limit: Optional[float] = None) -> Optional[Move]:
    """
    Iterative deepening: search from depth=1 up to max_depth or time_limit.
    Return best move found.
    """
    start_time = time.time()
    best_move = None
    for depth in range(1, max_depth+1):
        if time_limit is not None and (time.time() - start_time) >= time_limit:
            break

        moves_all = generate_moves(board, side, castling, en_passant)
        moves_legal = filter_legal_moves(board, moves_all, side, castling, en_passant)
        if not moves_legal:
            return None

        # simple move ordering: sort captures first
        def move_sort_key(mv: Move):
            return mv.captured != '.', piece_value(mv.captured)
        moves_legal.sort(key=move_sort_key, reverse=True)

        current_best = None
        if side == 'w':
            best_val = -math.inf
            alpha, beta = -math.inf, math.inf
            for mv in moves_legal:
                saved_cr = castling
                saved_ep = en_passant
                make_move(board, mv)
                new_cr = update_castling_rights(saved_cr, mv, board)
                new_ep = update_en_passant_square(mv, board)
                val = alpha_beta_tt(board, depth-1, alpha, beta, False,
                                    'b', new_cr, new_ep, halfmove, fullmove)
                undo_move(board, mv)
                castling = saved_cr
                en_passant = saved_ep
                if val > best_val:
                    best_val = val
                    current_best = mv
                alpha = max(alpha, val)
                if alpha >= beta:
                    break
        else:
            best_val = math.inf
            alpha, beta = -math.inf, math.inf
            for mv in moves_legal:
                saved_cr = castling
                saved_ep = en_passant
                make_move(board, mv)
                new_cr = update_castling_rights(saved_cr, mv, board)
                new_ep = update_en_passant_square(mv, board)
                val = alpha_beta_tt(board, depth-1, alpha, beta, True,
                                    'w', new_cr, new_ep, halfmove, fullmove)
                undo_move(board, mv)
                castling = saved_cr
                en_passant = saved_ep
                if val < best_val:
                    best_val = val
                    current_best = mv
                beta = min(beta, val)
                if alpha >= beta:
                    break

        if current_best:
            best_move = current_best

        if time_limit is not None and (time.time() - start_time) >= time_limit:
            break

    return best_move

#
# 50-move rule and repetition checks
#
def is_50move_rule(halfmove_clock: int) -> bool:
    """If halfmove_clock >= 100 => 50 move rule triggered => draw."""
    return halfmove_clock >= 100

def is_threefold_repetition(reps: Dict[int,int]) -> bool:
    """If any position has been repeated 3 or more times => draw."""
    return any(count >= 3 for count in reps.values())

#######################################################
# PART 5: TACTIC DETECTION & PRINTING
#######################################################

def detect_tactics(board: List[List[str]], side_just_moved: str, move: Move) -> List[str]:
    """Check if the move has created a fork/pin/skewer. Simplified demonstration."""
    messages = []
    # Check forks: how many captures does the moved piece threaten?
    piece_after = board[move.r2][move.c2]
    temp_moves = generate_moves_for_piece(board, move.r2, move.c2, piece_after,
                                          "", side_just_moved, (None,None))
    captures = sum(1 for mv in temp_moves if mv.captured != '.' and opposite_color(mv.piece, mv.captured))
    if captures >= 2:
        pos_label = coord_to_algebraic(move.r2, move.c2)
        piece_label = piece_after
        messages.append(
            f"{WARNING_COLOR}Fork detected! The {piece_label} on {pos_label} attacks multiple pieces.{RESET}"
        )

    # Very simplified pin/skewer check for line pieces only
    if piece_after.upper() in ['B','R','Q']:
        directions = []
        if piece_after.upper() == 'B':
            directions = [(-1,-1), (-1,1), (1,-1), (1,1)]
        elif piece_after.upper() == 'R':
            directions = [(-1,0), (1,0), (0,-1), (0,1)]
        else:  # 'Q'
            directions = [(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(-1,1),(1,-1),(1,1)]

        enemy_king = 'K' if side_just_moved=='b' else 'k'
        for dr, dc in directions:
            squares_line = []
            rr, cc = move.r2 + dr, move.c2 + dc
            while in_bounds(rr, cc):
                squares_line.append((rr, cc))
                if board[rr][cc] != '.':
                    break
                rr += dr
                cc += dc
            if squares_line:
                last_r, last_c = squares_line[-1]
                if board[last_r][last_c] == enemy_king:
                    in_between = squares_line[:-1]
                    blocked = [(x,y) for (x,y) in in_between if board[x][y] != '.']
                    if len(blocked) == 1:
                        pinned_piece = board[blocked[0][0]][blocked[0][1]]
                        pos_label_piece = coord_to_algebraic(blocked[0][0], blocked[0][1])
                        pos_label_king = coord_to_algebraic(last_r, last_c)
                        pos_label_self = coord_to_algebraic(move.r2, move.c2)
                        if piece_value(pinned_piece.upper()) < piece_value('K'):
                            messages.append(
                                f"{WARNING_COLOR}Pin detected! The {piece_after} on {pos_label_self} pinned {pinned_piece} at {pos_label_piece} to the King at {pos_label_king}.{RESET}"
                            )
                        else:
                            messages.append(
                                f"{WARNING_COLOR}Skewer detected! The {piece_after} on {pos_label_self} skewers {pinned_piece} at {pos_label_piece} with the King behind!{RESET}"
                            )

    return messages

def coord_to_algebraic(r, c) -> str:
    return chr(c + ord('a')) + str(8 - r)

def print_board(board: List[List[str]]):
    """Print a clean, aligned chessboard with no layout glitches across rows."""
    print("    a b c d e f g h")
    for r in range(8):
        row_str = f"{8 - r}   "
        for c in range(8):
            bg = color_square(r, c)
            piece = board[r][c]
            symbol = UNICODE_PIECES[piece]
            color = WHITE_PIECE_COLOR if is_white(piece) else BLACK_PIECE_COLOR if is_black(piece) else ""
            padded_symbol = f"{symbol:2}"
            cell = f"{bg}{color}{padded_symbol}{RESET}"
            row_str += cell
        row_str += f"  {8 - r}"
        print(row_str)
    print("    a b c d e f g h")

#######################################################
# PART 6: GAME FLOW, UI, MAIN LOOP
#######################################################

def user_to_move_coords(move_str: str) -> Optional[Tuple[int,int,int,int]]:
    """Parse e2e4 or e2 e4 -> (r1,c1,r2,c2)."""
    move_str = move_str.replace(" ","")
    if len(move_str) < 4:
        return None
    try:
        ffile = ord(move_str[0]) - ord('a')
        frank = 8 - int(move_str[1])
        tfile = ord(move_str[2]) - ord('a')
        trank = 8 - int(move_str[3])
        if not in_bounds(frank,ffile) or not in_bounds(trank,tfile):
            return None
        return (frank, ffile, trank, tfile)
    except:
        return None

def pick_promotion(piece: str) -> str:
    """Ask user which piece to promote to (Q, R, B, N)."""
    while True:
        choice = input("Promote to (Q, R, B, N)? ").strip().upper()
        if choice in ['Q','R','B','N']:
            return choice if piece.isupper() else choice.lower()
        print("Invalid choice. Try again.")

def print_splash_screen():
    print(f"{WHITE_PIECE_COLOR}Welcome to{RESET} {BLACK_PIECE_COLOR}Chess Simulator{RESET}!")
    print("Play a full game of chess vs the AI!")
    print("Type 'save filename' to save, 'load filename' to load, or 'quit' to exit.")
    print("Type 'hint' for a recommended move on White's turn.")
    print("Now with advanced AI features, iterative deepening, PST, transposition table!\n")

def save_game(filename: str, board: List[List[str]], side: str,
              castling_rights: str, en_passant: str,
              halfmove_clock: int, fullmove_number: int,
              move_history: List[str]):
    fen_str = board_to_fen(board, side, castling_rights, en_passant, halfmove_clock, fullmove_number)
    with open(filename, 'w') as f:
        f.write("[FEN]\n")
        f.write(fen_str+"\n")
        f.write("[MOVES]\n")
        for mh in move_history:
            f.write(mh+"\n")

def load_game(filename: str):
    with open(filename,'r') as f:
        lines = f.read().splitlines()
    fen_line = None
    move_lines = []
    mode = None
    for l in lines:
        if l.strip() == "[FEN]":
            mode = "fen"
            continue
        elif l.strip() == "[MOVES]":
            mode = "moves"
            continue
        if mode == "fen" and fen_line is None and l.strip():
            fen_line = l.strip()
        elif mode == "moves" and l.strip():
            move_lines.append(l.strip())
    if fen_line is None:
        raise ValueError("No FEN found in save file")

    b, stm, cr, ep, hmc, fmn = fen_to_board(fen_line)
    return b, stm, cr, ep, hmc, fmn, move_lines


def play_game_vs_ai(ai_depth=3, time_limit=None):
    board = starting_board()
    side_to_move = 'w'
    castling_rights = 'KQkq'
    en_passant = '-'
    halfmove_clock = 0
    fullmove_number = 1

    # For 3fold repetition tracking
    repetition_dict = {}
    def record_position():
        # We can store FEN or a hashed key
        fen_key = board_to_fen(board, side_to_move, castling_rights,
                               en_passant, halfmove_clock, fullmove_number)
        repetition_dict[fen_key] = repetition_dict.get(fen_key, 0) + 1

    move_history = []
    print_splash_screen()
    print_board(board)
    record_position()

    while True:
        # check for 50 move rule
        if is_50move_rule(halfmove_clock):
            print("50-move rule triggered! It's a draw.")
            print("Score: 0.5-0.5")
            break

        # check for threefold repetition
        if is_threefold_repetition(repetition_dict):
            print("Threefold repetition triggered! It's a draw.")
            print("Score: 0.5-0.5")
            break

        # Check checkmate/stalemate
        if is_checkmate(board, side_to_move, castling_rights, en_passant):
            if side_to_move == 'w':
                print(f"{WARNING_COLOR}Checkmate! Black wins!{RESET}")
                print("Score: 0-1")
            else:
                print(f"{WARNING_COLOR}Checkmate! White wins!{RESET}")
                print("Score: 1-0")
            break
        if is_stalemate(board, side_to_move, castling_rights, en_passant):
            print("Stalemate! It's a draw.")
            print("Score: 0.5-0.5")
            break

        if side_to_move == 'w':
            # Human's turn
            print("White to move. Example input: e2e4, or 'hint', or 'save'/'load'/'quit'")
            mv_str = input("> ").strip().lower()
            if mv_str in ('quit','exit'):
                print("Exiting game.")
                return
            elif mv_str.startswith("save"):
                parts = mv_str.split()
                filename = parts[1] if len(parts) > 1 else "chess_save.txt"
                save_game(filename, board, side_to_move, castling_rights,
                          en_passant, halfmove_clock, fullmove_number,
                          move_history)
                print(f"Game saved to '{filename}'.")
                continue
            elif mv_str.startswith("load"):
                parts = mv_str.split()
                filename = parts[1] if len(parts) > 1 else "chess_save.txt"
                try:
                    b, stm, cr, ep, hmc, fmn, mh = load_game(filename)
                    board = b
                    side_to_move = stm
                    castling_rights = cr
                    en_passant = ep
                    halfmove_clock = hmc
                    fullmove_number = fmn
                    move_history = mh
                    repetition_dict.clear()
                    record_position()
                    print_board(board)
                    continue
                except Exception as e:
                    print(f"Failed to load: {e}")
                    continue
            elif mv_str == "hint":
                recommendation = iterative_deepening_search(board, 'w',
                                                            castling_rights, en_passant,
                                                            halfmove_clock, fullmove_number,
                                                            max_depth=ai_depth,
                                                            time_limit=time_limit)
                if recommendation:
                    print(f"Hint: A good move might be {algebraic_notation(recommendation)}")
                else:
                    print("No legal moves for a hint.")
                continue

            coords = user_to_move_coords(mv_str)
            if coords is None:
                print("Invalid move format. Try again.")
                continue

            r1,c1,r2,c2 = coords
            piece = board[r1][c1]
            if piece=='.' or not is_white(piece):
                print("That's not a valid white piece. Try again.")
                continue

            pseudo = generate_moves_for_piece(board, r1, c1, piece,
                                              castling_rights, side_to_move,
                                              (None, None))
            legal_moves = filter_legal_moves(board, pseudo, side_to_move,
                                             castling_rights, en_passant)
            chosen_move = None
            for mv in legal_moves:
                if mv.r2==r2 and mv.c2==c2:
                    chosen_move = mv
                    break
            if not chosen_move:
                print("Illegal move. Try again.")
                continue

            if chosen_move.promotion:
                promo_choice = pick_promotion(piece)
                chosen_move.promotion = promo_choice

            make_move(board, chosen_move)
            # Tactic detection
            tactics = detect_tactics(board, side_to_move, chosen_move)
            for msg in tactics:
                print(msg)
            castling_rights = update_castling_rights(castling_rights, chosen_move, board)
            en_passant = update_en_passant_square(chosen_move, board)
            if piece.upper()=='P' or chosen_move.captured!='.':
                halfmove_clock = 0
            else:
                halfmove_clock += 1

            notation = algebraic_notation(chosen_move)
            if side_to_move=='w':
                move_history.append(f"{fullmove_number}. {notation}")
            else:
                move_history[-1] += f" {notation}"
            if side_to_move=='b':
                fullmove_number += 1

            side_to_move = 'b'
            print_board(board)
            record_position()

        else:
            # AI's turn
            print("Black (AI) is thinking...")
            best_mv = iterative_deepening_search(board, 'b',
                                                 castling_rights, en_passant,
                                                 halfmove_clock, fullmove_number,
                                                 max_depth=ai_depth,
                                                 time_limit=time_limit)
            if not best_mv:
                # no legal moves => checkmate or stalemate
                side_to_move = 'w'
                continue

            make_move(board, best_mv)
            tactics = detect_tactics(board, side_to_move, best_mv)
            for msg in tactics:
                print(msg)
            castling_rights = update_castling_rights(castling_rights, best_mv, board)
            en_passant = update_en_passant_square(best_mv, board)
            if best_mv.piece.upper()=='P' or best_mv.captured!='.':
                halfmove_clock = 0
            else:
                halfmove_clock += 1
            notation = algebraic_notation(best_mv)
            if side_to_move=='w':
                move_history.append(f"{fullmove_number}. {notation}")
            else:
                move_history[-1] += f" {notation}"
                fullmove_number += 1

            side_to_move = 'w'
            print_board(board)
            record_position()

def main():
    # For example, we do depth=4 and no time limit. Adjust as you see fit.
    play_game_vs_ai(ai_depth=4, time_limit=None)

if __name__ == "__main__":
    main()
