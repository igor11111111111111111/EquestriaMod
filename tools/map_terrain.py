# The shape of the world in one place: both the heightmap for the editor and the settlement coordinates are computed
# from here, otherwise a town ends up at the wrong height and hangs in the air or sinks.
import numpy as np

SEA_LEVEL = 0.35        # fraction of height, below it - water
PLAIN = 0.45            # the plain on which settlements stand
MOUNTAIN = 0.85         # mountain peaks
SEED = 20260916

# Areas for settlements: fraction of the map size (x, y) and the radius of the flat area
PLATEAUS = [
    (0.38, 0.42, 0.045),   # Canterlot
    (0.58, 0.58, 0.035),   # Ponyville
]


def height_field(size):
    """Normalized heightmap 0..1, origin at the lower left corner of the map."""
    yy, xx = np.mgrid[0:size, 0:size]
    u, v = xx / (size - 1), yy / (size - 1)

    r = np.sqrt(((u - 0.5) * 1.15) ** 2 + ((v - 0.5) * 1.0) ** 2)
    island = np.clip(1.0 - (r / 0.46) ** 2, 0.0, 1.0)

    rng = np.random.default_rng(SEED)
    noise = np.zeros((size, size), dtype=np.float32)
    amp = 1.0
    for cells in (4, 8, 16, 32):
        grid = rng.random((cells + 1, cells + 1)).astype(np.float32)
        gy = np.clip(v * cells, 0, cells - 1e-3)
        gx = np.clip(u * cells, 0, cells - 1e-3)
        y0, x0 = gy.astype(int), gx.astype(int)
        ty, tx = gy - y0, gx - x0
        sy, sx = ty * ty * (3 - 2 * ty), tx * tx * (3 - 2 * tx)
        top = grid[y0, x0] * (1 - sx) + grid[y0, x0 + 1] * sx
        bot = grid[y0 + 1, x0] * (1 - sx) + grid[y0 + 1, x0 + 1] * sx
        noise += (top * (1 - sy) + bot * sy) * amp
        amp *= 0.5
    noise = (noise - noise.min()) / (noise.max() - noise.min())

    height = SEA_LEVEL - 0.20 + island * (PLAIN - SEA_LEVEL + 0.22)
    north = np.clip((0.30 - v) / 0.16, 0.0, 1.0)
    east = np.clip((u - 0.74) / 0.16, 0.0, 1.0)
    ridge = np.clip(north + east, 0.0, 1.0)
    ridge = ridge * ridge * (3 - 2 * ridge) * island
    height += ridge * (MOUNTAIN - PLAIN) * (0.5 + 0.5 * noise)
    height += (noise - 0.5) * 0.06 * island

    for px, py, rad in PLATEAUS:
        d = np.sqrt((u - px) ** 2 + (v - py) ** 2)
        w = np.clip(1.0 - d / rad, 0.0, 1.0) ** 0.5
        height = height * (1 - w) + (PLAIN + 0.02) * w

    return np.clip(height, 0.0, 1.0)


def sample(field, u, v):
    """Height (0..1) at a point given in map fractions."""
    size = field.shape[0]
    x = int(np.clip(u * (size - 1), 0, size - 1))
    y = int(np.clip(v * (size - 1), 0, size - 1))
    return float(field[y, x])


def to_meters(norm_value, field, min_height, max_height):
    """Converts a normalized height to meters the same way the editor import did."""
    lo, hi = float(field.min()), float(field.max())
    if hi - lo < 1e-6:
        return min_height
    return min_height + (norm_value - lo) / (hi - lo) * (max_height - min_height)
