/*
 * collision_logic.h - what the collision overlay (collision_mod.c;
 * openspec change collision-overlay, D7 and D8) computes from the game's
 * baked collision, on bytes, so scripts/test_collision_overlay.py can drive
 * it without the game.
 *
 * The data (openspec change collision-spike, section 2): sub_001642A0
 * bakes every area's collision tree into 0x48-byte world triangles
 * (wall_logic.h has the record) and builds an octree over them, both in
 * the bake's space (RotX(pi) of tree space, Y down), which is also the
 * player's and the renderer's world space.
 *
 * The look is the Godot collision view's (xboxrecomp-cli
 * extract/collision.py): the class colour or a flatness band, shaded
 * 0.3 + 0.7 |n.L|, and the crease and open edges of each class.
 */
#ifndef CAT_COLLISION_LOGIC_H
#define CAT_COLLISION_LOGIC_H

#include <stdint.h>

/* The three buffers sub_001642A0 fills, back to back in .bss, and their
 * counts. A buffer's capacity is the room before the next one. */
#define COL_REF_BUF     0x00BACB98u     /* (tri*, next) cells */
#define COL_REF_SIZE    8u
#define COL_AABB_MIN    0x00C21E98u     /* the world box's min, after the cells */
#define COL_TRI_BUF     0x00C21EA8u
#define COL_TRI_SIZE    0x48u
#define COL_NODE_BUF    0x00CAE8A8u
#define COL_NODE_SIZE   0x38u
#define COL_TRI_COUNT   0x00CC9E2Cu     /* u32 */
#define COL_NODE_COUNT  0x00CC9E30u     /* u32 */
#define COL_REF_COUNT   0x00CCA048u     /* u32 */
#define COL_MEM_END     (COL_REF_COUNT + 4u)

#define COL_TRI_MAX     ((int)((COL_NODE_BUF - COL_TRI_BUF) / COL_TRI_SIZE))    /* 8000 */
#define COL_NODE_MAX    ((int)((COL_TRI_COUNT - COL_NODE_BUF) / COL_NODE_SIZE)) /* 1999 */
#define COL_REF_MAX     ((int)((COL_AABB_MIN - COL_REF_BUF) / COL_REF_SIZE))    /* 60000 */

/* An octree node: 8 child pointers (0 for none) at +0x00..+0x1C, the
 * reference list's head and count at +0x20 and +0x24, the centre at
 * +0x28 and the half-size at +0x34. Node 0 is the root. */
#define COL_NODE_KIDS   0x00u
#define COL_NODE_HEAD   0x20u
#define COL_NODE_NREF   0x24u
#define COL_NODE_CENTRE 0x28u
#define COL_NODE_HALF   0x34u
/* A triangle goes into a child when it touches the child's box grown to
 * h * 0.5 + 0.1 (sub_001647C0): the walk grows each box by this much. */
#define COL_NODE_PAD    0.1f

/* The Godot view's constants (extract/collision.py). */
#define COL_WELD        1e-3f           /* WELD */
#define COL_CREASE_DEG  20.0f           /* CREASE_DEG */
#define COL_AMBIENT     0.3f            /* AMBIENT */
#define COL_ALPHA       0.35f           /* DEBUG_ALPHA */
#define COL_EDGE_DARKEN 0.3f            /* EDGE_DARKEN */

/* The flatness bands (FLAT_BANDS 0.1, 2, 10 degrees, FLAT_NAMES), then the
 * sliver's own. */
enum { COL_FLAT, COL_NEAR, COL_TILTED, COL_SLOPE, COL_SLIVER, COL_BANDS };
extern const float col_band_deg[COL_SLIVER - 1];
extern const char *const col_band_name[COL_BANDS];
extern const uint32_t col_band_rgb[COL_BANDS];

/* One baked triangle with what the overlay draws it with. */
struct col_tri {
    float v[3][3];
    float n[3];                 /* from the corners; 0 when degenerate */
    float c[3], r;              /* bounding sphere: centroid, farthest corner */
    float shade;                /* COL_AMBIENT..1 */
    uint32_t cls;               /* the low 24 bits of +0x24 */
    uint8_t ok;                 /* a non-zero normal: drawn */
    uint8_t band;               /* COL_FLAT..COL_SLIVER */
    uint8_t edges;              /* bit k: draw edge v[k] -> v[(k + 1) % 3] */
};

struct col_stage {
    int n;                      /* triangles loaded */
    uint32_t key;               /* col_stage_key when loaded */
    int creases, opens;         /* edges drawn, for the log */
    struct col_tri t[COL_TRI_MAX];
};

/* The unit normal of corners v (cross(v1 - v0, v2 - v0), as sub_00165200
 * and the extract compute it); 0 and n zero when it is degenerate. */
int col_normal(const float v[3][3], float n[3]);
/* Degrees the face is off exactly flat or exactly vertical, whichever is
 * nearer (BLiNX's up is +-Y). */
float col_flatness_deg(const float n[3]);
/* The band of a face deg off: the count of thresholds at or below deg. */
int col_band(float deg);
/* Whether two corners are within COL_WELD of each other on every axis. */
int col_sliver(const float v[3][3]);
/* 0.3 + 0.7 |n.L|, L the extract's light (0.5, 1, 0.25) in the bake's
 * space (y and z negated); |n.L| makes the sign of L irrelevant. */
float col_shade(const float n[3]);
/* c times s per channel, 0xRRGGBB. */
uint32_t col_scale_rgb(uint32_t rgb, float s);

/* What identifies the stage's bake without copying it: the count and a
 * hash of the geometry and class of every 16th record and the last one
 * (the query stamp at +0x28 changes every query and is left out). mem is
 * guest memory from address 0, at least COL_MEM_END bytes. */
uint32_t col_stage_key(const uint8_t *mem);

/* Loads the baked triangles (at most COL_TRI_MAX) and computes each
 * one's normal, sphere, shade, band and edges: the crease and open edges
 * of each class, corners welded within COL_WELD, as crease_edges does.
 * Returns the count. */
int col_stage_load(struct col_stage *s, const uint8_t *mem);

/* The triangles whose sphere meets the sphere (c, r): the octree walked
 * from node 0, each node's box (centre +- half + COL_NODE_PAD) tested
 * against the sphere, each reference list followed for at most its count
 * and every pointer checked against its buffer and the counts, so a bake
 * in progress yields fewer triangles, never a bad read. mark[] (s->n
 * entries, the caller's) holds the walk's stamp per triangle: a triangle
 * is listed once per stamp value. Writes up to cap indices to out and
 * returns how many. */
int col_query(const struct col_stage *s, const uint8_t *mem, const float c[3], float r,
              uint32_t *mark, uint32_t stamp, int *out, int cap);

#endif
