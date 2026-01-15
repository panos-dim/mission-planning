#!/usr/bin/env python3
"""Compare opportunity counts between frontend and backend"""

frontend = {
    'T1': 15, 'T2': 7, 'T3': 15, 'T4': 5, 'T5': 17, 'T6': 6, 'T7': 9,
    'T9': 13, 'T10': 5, 'T11': 20, 'T12': 6, 'T13': 1, 'T14': 3,
    'T15': 20, 'T16': 3, 'T17': 3, 'T18': 3, 'T19': 1, 'T20': 4,
    'T21': 5, 'T22': 2, 'T23': 6, 'T24': 6, 'T25': 6, 'T26': 10,
    'T27': 3, 'T28': 4, 'T29': 2, 'T30': 18, 'T32': 3, 'T33': 17,
    'T34': 9, 'T35': 3, 'T36': 4, 'T37': 6, 'T38': 6, 'T39': 6,
    'T40': 3, 'T41': 3, 'T42': 3, 'T43': 21, 'T44': 2, 'T45': 4,
    'T46': 3, 'T47': 5, 'T48': 20, 'T49': 3, 'T50': 6
}

backend = {
    'T1': 16, 'T2': 8, 'T3': 15, 'T4': 6, 'T5': 17, 'T6': 6, 'T7': 8,
    'T9': 13, 'T10': 6, 'T11': 20, 'T12': 6, 'T13': 1, 'T14': 3,
    'T15': 20, 'T16': 3, 'T17': 3, 'T18': 3, 'T19': 2, 'T20': 4,
    'T21': 4, 'T22': 2, 'T23': 6, 'T24': 6, 'T25': 7, 'T26': 11,
    'T27': 4, 'T28': 3, 'T29': 1, 'T30': 18, 'T32': 3, 'T33': 17,
    'T34': 10, 'T35': 3, 'T36': 5, 'T37': 6, 'T38': 6, 'T39': 6,
    'T40': 3, 'T41': 3, 'T42': 2, 'T43': 21, 'T44': 2, 'T45': 4,
    'T46': 3, 'T47': 5, 'T48': 20, 'T49': 3, 'T50': 6
}

print("Differences (Backend - Frontend):")
print("=" * 50)
total_diff = 0
for target in sorted(frontend.keys()):
    f = frontend[target]
    b = backend[target]
    diff = b - f
    if diff != 0:
        print(f"{target}: Frontend={f}, Backend={b}, Diff={diff:+d}")
        total_diff += diff

print("=" * 50)
print(f"Total difference: {total_diff}")
print(f"Frontend total: {sum(frontend.values())}")
print(f"Backend total: {sum(backend.values())}")
