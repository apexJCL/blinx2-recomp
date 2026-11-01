/*
 * wall_logic.h - the thin-wall rule of the walls mod (walls_mod.c;
 * openspec change collision-spike, task 1.7), on copies of the baked
 * collision triangles so scripts/test_walls.py can drive it without the
 * game.
 *
 * The game's sphere query (sub_00165630 per triangle, under the walk
 * sub_00165380) keeps one best value for every contact: a vertex or edge
 * by its distance, a face by its signed distance s = dot(c - v0, n). The
 * smallest wins, so a face the centre is behind (s < 0) beats everything,
 * and of two such faces the deeper one wins. In a wall thinner than twice
 * the radius, a centre that entered by the near face F is deeper behind
 * the far face B while it is less than half-way in, and B's push carries
 * it out of the far side.
 *
 * The rule: when the game takes a face X the centre is behind, and the
 * previous centre was behind X too, look for the face the centre entered
 * by: one facing the other way (n_X . n_Y < -0.5) whose plane is within r,
 * whose triangle holds the centre's projection, and whose front side the
 * previous centre was on. If there is one, that face is the contact. With
 * none (a one-sided platform jumped into from below, a centre already
 * inside), the game's choice stands.
 */
#ifndef CAT_WALL_LOGIC_H
#define CAT_WALL_LOGIC_H

#include <stdint.h>

/* The baked triangles (sub_00164850's buffer), 0x48 bytes each: v0 +0x00,
 * v1 +0x0C, v2 +0x18, class +0x24 (the strip colour 0xRRGGBB in the low
 * 24 bits), query stamp +0x28, normal +0x2C, centroid +0x38, bounding
 * radius +0x44. */
#define WALL_TRI_BUF    0x00C21EA8u
#define WALL_TRI_SIZE   0x48u
#define WALL_TRI_COUNT  0x00CC9E2Cu     /* u32 */
/* The records that fit between the buffer and its count. */
#define WALL_TRI_MAX    ((int)((WALL_TRI_COUNT - WALL_TRI_BUF) / WALL_TRI_SIZE))

/* sub_00165630's flag bits: vertices, edges, the face. The player passes
 * 7: edges and the face (bit 0 is not read by the test). */
#define WALL_FLAG_FACE  2u
#define WALL_FLAG_EDGES 4u
#define WALL_FLAG_VERTS 8u

/* The classes the triangle test skips when their switch is set, and the
 * one it always skips (sub_00165630's class checks). */
#define WALL_CLASS_A    0x7F7F00u       /* [0x65B1E0] */
#define WALL_CLASS_B    0xFF00FFu       /* [0x65B1E8] */
#define WALL_CLASS_C    0x0000FFu       /* [0x65B1EC] */
#define WALL_CLASS_D    0x00FFFFu       /* [0x65B1F0] */
#define WALL_CLASS_NONE 0xFFFFFFu

/* How far behind a plane the previous centre may be and still count as in
 * front of it (float noise on a centre resting on the face). */
#define WALL_EPS        0.01f

/* A step longer than this many radii between the previous position and
 * this one is a respawn or a warp, not movement: the rule does not look. */
#define WALL_STEP_MAX   2.0f

struct wall_tri {
    float v[3][3];
    float n[3];
    float centroid[3];
    float radius;
    uint32_t cls;
};

/* What one triangle test writes when it takes a contact: the point, the
 * normal, the push, the best value and the class (the whole u32 at +0x24,
 * as the game copies it). */
struct wall_contact {
    float p[3], n[3], pen, best;
    uint32_t cls;
    int tri;
};

/* What wall_decide asks of the hook: leave the game's outputs, put back
 * the ones from before the test, or write *out. */
enum { WALL_KEEP, WALL_RESTORE, WALL_WRITE };

/* Unpack one baked record (WALL_TRI_SIZE bytes, little endian). */
void wall_tri_load(struct wall_tri *t, const uint8_t *rec);

/* Signed distance of p from t's plane: dot(p - v0, n). */
float wall_s(const struct wall_tri *t, const float p[3]);

/* Whether c's projection on t's plane (c - n * s) lies in the triangle,
 * edges included, as the game's face test decides it. */
int wall_inside(const struct wall_tri *t, const float c[3], float s);

/* Whether the game's test skips t's class; sw holds the four switches
 * [0x65B1E0], [0x65B1E8], [0x65B1EC], [0x65B1F0]. */
int wall_skipped(uint32_t cls, const uint32_t sw[4]);

/* The rule above for the face x the game just took with the centre behind
 * it: the index of the face the sphere entered by, or -1 to keep x. Of
 * several, the one with the smallest s (the game's own order among them).
 * A face whose normal is not unit length (zero, NaN) is never x nor y. */
int wall_entry_face(const struct wall_tri *tris, int n, int x, const float c[3],
                    const float prev[3], float r, const uint32_t sw[4]);

/* t's best vertex or edge contact for centre c, as sub_00030230 (a vertex
 * within r) and sub_00030070 (an edge within r whose closest point lies on
 * it) take them under flags, the smaller distance first. Returns 1 and
 * fills *out (best the distance, pen r - dist, as the game writes them),
 * or 0 with none. */
int wall_vertex_edge(const struct wall_tri *t, int ti, const float c[3], float r, uint32_t flags,
                     struct wall_contact *out);

/* The fix's whole decision, after a triangle test on x took a contact:
 * best0 the walk's best before the test, best after it, delta the
 * player's step (pos - prev; NULL for none), push_k the game's face push
 * factor. It acts only when the test took x's face with the centre behind
 * it and wall_entry_face finds the face y the sphere came in by (*y, else
 * -1). The contact is then the smallest of y's face, x's own vertex or
 * edge and whatever the walk held before, with the game's tie rule (a
 * later contact must be strictly smaller): WALL_WRITE with *out for y or
 * for x's vertex or edge, WALL_RESTORE for the earlier one. */
int wall_decide(const struct wall_tri *tris, int n, int x, const float c[3], const float delta[3],
                float r, uint32_t flags, const uint32_t sw[4], float best0, float best,
                float push_k, struct wall_contact *out, int *y);

/* Back-to-back pairs for the probe: f a wall face (|n.y| < 0.7) and b one
 * facing the other way (n_f . n_b < -0.9) behind f's centroid, holding its
 * projection, less than wmax away. Returns b, or -1, and the thickness in
 * *w. */
int wall_pair(const struct wall_tri *tris, int n, int f, float wmax, const uint32_t sw[4],
              float *w);

#endif
