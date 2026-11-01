#!/usr/bin/env python3
"""Tests for the entity API and the entities mod (mods."entities.*",
openspec change entity-mod-api).

Compiles a driver against src/ent_api_logic.c over a fake guest memory and
checks the rules: the spawn guards in their order and each status, the cap,
the class allowlist, record allocation and the area-setup free (referenced
records kept), the placement copy and its respawn nibble, the spawn's
verify, handle validity across a respawn and a slot reuse, the list walk
on odd addresses and a broken chain, the kill guards, and the class-1 hp
override's apply and restore, the area sweep's unlink and its safety net
(a short or looped walk, the early out that reads only the used bytes),
records kept retired across retries and freed at a stage start, and
whether a kill's hit took. Then, with the toolkit beside the project,
ent_api.c itself over a fake mod API: kills answered once each, after
enemy updates rather than frames; the sweep kept running when the mod is
switched off after a spawn; a session that never spawned left stock; the
hp clamp and NULL pointers. Then checks the keys: each setting and
control have a CONFIG env row and a docs/env.md row, the descriptor names
them, the golden check knows the switch's stock value, and the hook slot
and the area-setup wrapper are in place.

  python3 scripts/test_entities.py
  uv run pytest scripts/test_entities.py

The C tests skip when no C compiler is on PATH.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

import pytest
import tomllib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
SRC = os.path.join(ROOT, "src")

STATUS = [
    "OK",
    "OFF",
    "BUSY",
    "TIMEOUT",
    "TIME_CONTROL",
    "CAP",
    "CLASS",
    "RECORDS",
    "GONE",
    "DEAD",
    "MODE",
    "LEAK",
    "CALL",
    "IGNORED",
]

# setting name -> (env row, kind in the descriptor)
SETTINGS = {
    "enable": ("RECOMP_ENTITIES", "XBOX_SET_ENUM"),
    "hp_scale": ("RECOMP_ENTITIES_HP_SCALE", "XBOX_SET_INT"),
}
# control id -> env row
CONTROLS = {
    "spawn": "RECOMP_ENTITIES_SPAWN_KEY",
    "kill": "RECOMP_ENTITIES_KILL_KEY",
}

# A fake guest: 16 MiB, the list's nodes at NODES, its objects one byte past
# a pool slot's used byte (odd addresses, as in the game), source placements
# at PL, the API's record block at REC. Each command builds its own scene
# and prints one line.
DRIVER = r"""
#define _DEFAULT_SOURCE     /* mmap's MAP_ANON and sysconf under -std=c11 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#if !defined(_WIN32)
#include <sys/mman.h>
#include <unistd.h>
#endif
#include "ent_api_logic.h"

#define MEM     0x01000000u
#define NODES   0x00B00000u
#define OBJS    0x00C00001u     /* odd: a used byte, then the object */
#define OBJ_SZ  0x100u
#define PL      0x00466000u
#define TAB     0x00480000u
#define REC     0x00E00000u

static uint8_t *g;
static struct entl_mem m;

static void w32(uint32_t va, uint32_t v) { memcpy(g + va, &v, 4); }
static void w16(uint32_t va, int16_t v) { memcpy(g + va, &v, 2); }
static void wf(uint32_t va, float v) { memcpy(g + va, &v, 4); }
static float rf(uint32_t va) { float v; memcpy(&v, g + va, 4); return v; }

static uint32_t obj_va(int i) { return OBJS + (uint32_t)i * OBJ_SZ; }
static uint32_t pl_va(int i) { return PL + (uint32_t)i * ENTL_PL_SIZE; }

/* n enemies, enemy i from placement i with id 100 + i and hp 3. */
static void scene(int n)
{
    int i;

    memset(g, 0, MEM);
    for (i = 0; i < 8; i++) {
        w32(pl_va(i), i == 5 ? 0x14 : i == 6 ? 0x21 : 1);
        wf(pl_va(i) + ENTL_PL_POS, 10.0f * (float)i);
        wf(pl_va(i) + ENTL_PL_ROT_Y, 0.5f);
        w32(pl_va(i) + ENTL_PL_MODE, 0x10ABCDEFu);
    }
    w32(ENTL_LIST, n ? NODES : 0);
    for (i = 0; i < n; i++) {
        uint32_t node = NODES + (uint32_t)i * 12u, o = obj_va(i);

        w32(node, i ? node - 12u : 0);
        w32(node + 4, i + 1 < n ? node + 12u : 0);
        w32(node + 8, o);
        g[o - 1] = 1;
        w32(o + ENTL_OB_LIST, ENTL_LIST);
        w32(o + ENTL_OB_CLASS, 1);
        w32(o + ENTL_OB_STATE, 2);
        w32(o + ENTL_OB_PLACEMENT, pl_va(i % 5));
        w16(o + ENTL_OB_ID, (int16_t)(100 + i));
        w16(o + ENTL_OB_HP, 3);
        w16(o + ENTL_OB_HP_MAX, 3);
        wf(o + ENTL_OB_POS, 1.0f + (float)i);
        wf(o + ENTL_OB_POS + 4, 2.0f);
        wf(o + ENTL_OB_POS + 8, 3.0f);
    }
    w32(ENTL_LIST_TAIL, n ? NODES + (uint32_t)(n - 1) * 12u : 0);
    w32(ENTL_LIST_COUNT, (uint32_t)n);
    /* Stage 3: two records at PL. */
    w32(ENTL_STAGE_TABLE + 12, TAB);
    w32(TAB, 2);
    w32(TAB + 4, PL);
}

/* What sub_0004EE20 does on success: a node at the tail for a new object
 * that points at the placement. */
static uint32_t game_append(uint32_t placement, int16_t id)
{
    uint32_t objs[ENTL_MAX_NODES];
    int n = entl_walk(&m, objs, ENTL_MAX_NODES);
    uint32_t node = NODES + (uint32_t)n * 12u, o = obj_va(n);

    if (n)
        w32(NODES + (uint32_t)(n - 1) * 12u + 4, node);
    else
        w32(ENTL_LIST, node);
    w32(node, n ? NODES + (uint32_t)(n - 1) * 12u : 0);
    w32(node + 4, 0);
    w32(node + 8, o);
    w32(ENTL_LIST_TAIL, node);
    g[o - 1] = 1;
    w32(o + ENTL_OB_LIST, ENTL_LIST);
    w32(o + ENTL_OB_PLACEMENT, placement);
    w16(o + ENTL_OB_ID, id);
    w32(ENTL_LIST_COUNT, (uint32_t)n + 1u);
    return o;
}

static struct ent_spawn_spec from_obj(int i)
{
    struct ent_spawn_spec s;

    memset(&s, 0, sizeof s);
    s.from = entl_handle(&m, obj_va(i));
    s.stage = s.record = -1;
    return s;
}

static int check(int leaked, const struct ent_spawn_spec *s)
{
    struct entl_plan p;

    return (int)entl_spawn_check(&m, REC, leaked, s, &p);
}

int main(void)
{
    char cmd[16];

    g = calloc(1, MEM);
    m.base = g;
    m.size = MEM;
    while (scanf("%15s", cmd) == 1) {
        if (!strcmp(cmd, "guards")) {
            /* Each guard alone, in the design's order (D4): a scene that
             * breaks two answers the earlier one. */
            struct ent_spawn_spec s;
            int i;

            scene(3);
            s = from_obj(0);
            printf("%d", check(1, &s));
            w32(ENTL_PLAY_MODE, 0x1000);
            printf(" %d", check(0, &s));
            w32(ENTL_TEAM_MODE, ENTL_TEAM_VS);
            printf(" %d", check(0, &s));
            w32(ENTL_PLAY_MODE, 0);
            printf(" %d", check(0, &s));
            w32(ENTL_TEAM_MODE, 0);
            s.from.id = 7;
            printf(" %d", check(0, &s));
            s = from_obj(0);
            w32(obj_va(0) + ENTL_OB_PLACEMENT, pl_va(5));
            s = from_obj(0);
            printf(" %d", check(0, &s));
            w32(obj_va(0) + ENTL_OB_PLACEMENT, pl_va(0));
            s = from_obj(0);
            w32(ENTL_LIST_COUNT, ENTL_POOL_SLOTS);
            printf(" %d", check(0, &s));
            w32(ENTL_LIST_COUNT, 3);
            for (i = 0; i < (int)ENTL_RECORDS; i++)
                g[REC + ENTL_RECORDS * ENTL_PL_SIZE + (uint32_t)i] = 1;
            printf(" %d", check(0, &s));
            memset(g + REC + ENTL_RECORDS * ENTL_PL_SIZE, 0, ENTL_RECORDS);
            printf(" %d\n", check(0, &s));
        } else if (!strcmp(cmd, "cap")) {
            /* The last slot is free to take; a full pool is not. */
            struct ent_spawn_spec s;

            scene(3);
            s = from_obj(0);
            w32(ENTL_LIST_COUNT, ENTL_POOL_SLOTS - 1);
            printf("%d", check(0, &s));
            w32(ENTL_LIST_COUNT, ENTL_POOL_SLOTS);
            printf(" %d\n", check(0, &s));
        } else if (!strcmp(cmd, "table")) {
            /* By stage table record: in range, past the count, no stage. */
            struct ent_spawn_spec s;
            struct entl_plan p;

            scene(1);
            memset(&s, 0, sizeof s);
            s.stage = 3;
            s.record = 1;
            printf("%d %X", (int)entl_spawn_check(&m, REC, 0, &s, &p), p.src_placement);
            s.record = 2;
            printf(" %d", check(0, &s));
            s.stage = 4;
            s.record = 0;
            printf(" %d", check(0, &s));
            s.stage = 60;
            printf(" %d\n", check(0, &s));
        } else if (!strcmp(cmd, "allowed")) {
            int c, first = 1;

            for (c = 0; c < 0x200; c++)
                if (entl_class_allowed((uint32_t)c)) {
                    printf("%s%X", first ? "" : " ", c);
                    first = 0;
                }
            printf("\n");
        } else if (!strcmp(cmd, "write")) {
            /* The copy: the source record, then the position (the spec's,
             * else the source enemy's), rot_y, the respawn nibble. */
            struct ent_spawn_spec s;
            struct entl_plan p;
            uint32_t r0, r1, r2;

            scene(3);
            s = from_obj(2);
            s.has_pos = 1;
            s.pos[0] = 40.0f;
            s.pos[1] = 50.0f;
            s.pos[2] = 60.0f;
            s.has_rot = 1;
            s.rot_y = 1.25f;
            entl_spawn_check(&m, REC, 0, &s, &p);
            entl_spawn_write(&m, REC, &p, &s);
            r0 = p.rec_placement;
            s = from_obj(2);
            entl_spawn_check(&m, REC, 0, &s, &p);
            entl_spawn_write(&m, REC, &p, &s);
            r1 = p.rec_placement;
            s = from_obj(2);
            s.respawn = ENT_RESPAWN_KEEP;
            entl_spawn_check(&m, REC, 0, &s, &p);
            entl_spawn_write(&m, REC, &p, &s);
            r2 = p.rec_placement;
            printf("%X %X %X | %X %.2f %.2f %.2f %.2f %08X | %.2f %.2f %.2f %.2f %08X | %08X | %d%d%d%d\n",
                   r0 - REC, r1 - REC, r2 - REC, g[r0] | g[r0 + 1] << 8, (double)rf(r0 + 4),
                   (double)rf(r0 + 8), (double)rf(r0 + 12), (double)rf(r0 + ENTL_PL_ROT_Y),
                   *(uint32_t *)(g + r0 + ENTL_PL_MODE), (double)rf(r1 + 4), (double)rf(r1 + 8),
                   (double)rf(r1 + 12), (double)rf(r1 + ENTL_PL_ROT_Y),
                   *(uint32_t *)(g + r1 + ENTL_PL_MODE), *(uint32_t *)(g + r2 + ENTL_PL_MODE),
                   entl_rec_used(&m, REC, 0), entl_rec_used(&m, REC, 1),
                   entl_rec_used(&m, REC, 2), entl_rec_used(&m, REC, 3));
        } else if (!strcmp(cmd, "verify")) {
            /* The game appended the record's object: OK and its handle.
             * Count unchanged, or a tail that is not the record's: LEAK. */
            struct ent_spawn_spec s;
            struct entl_plan p;
            struct ent_handle h = { 0, 0, 0 };
            uint32_t o;
            int a, b, c;

            scene(3);
            s = from_obj(0);
            entl_spawn_check(&m, REC, 0, &s, &p);
            entl_spawn_write(&m, REC, &p, &s);
            a = (int)entl_spawn_verify(&m, &p, &h);
            o = game_append(p.rec_placement, 555);
            b = (int)entl_spawn_verify(&m, &p, &h);
            printf("%d %d %d %d %d", a, b, h.obj == o, h.placement == p.rec_placement, h.id);
            w32(o + ENTL_OB_PLACEMENT, pl_va(1));
            c = (int)entl_spawn_verify(&m, &p, &h);
            printf(" %d\n", c);
        } else if (!strcmp(cmd, "records")) {
            /* Records are not reused within a stage; an area setup marks
             * them, the sweep retires the ones no listed object points at,
             * a retry's or a rewind's copy of a retired one goes off the
             * list again, a second retry's setup keeps them retired, and
             * only a stage start frees them. */
            struct ent_spawn_spec s;
            struct entl_plan p;
            struct entl_sweep r;
            int i, a, done;

            scene(2);
            for (i = 0; i < 3; i++) {
                s = from_obj(0);
                entl_spawn_check(&m, REC, 0, &s, &p);
                entl_spawn_write(&m, REC, &p, &s);
            }
            game_append(entl_rec_va(REC, 1), 300);
            printf("%d %d %d", entl_rec_free_index(&m, REC), entl_rec_listed(&m, REC),
                   entl_rec_stale(&m, REC) != 0);
            /* A retry's setup marks all three; the sweep takes record 1's
             * copy off the list (the restore brought it back) and retires
             * all three. */
            a = entl_rec_age(&m, REC, 0);
            done = entl_area_sweep(&m, REC, 0, &r);
            printf(" %d %d %d %d %d%d%d %d %d", a, done, r.unlisted, r.freed,
                   entl_rec_used(&m, REC, 0), entl_rec_used(&m, REC, 1),
                   entl_rec_used(&m, REC, 2), entl_rec_free_index(&m, REC), entl_count(&m));
            /* A rewind brings back an object of record 2, retired above:
             * not stale, and the next sweep takes it off the list. */
            game_append(entl_rec_va(REC, 2), 301);
            i = entl_rec_stale(&m, REC) != 0;
            done = entl_area_sweep(&m, REC, 0, &r);
            printf(" %d %d %d %d %u", i, done, r.unlisted, r.freed, entl_count(&m));
            /* A second retry from the same checkpoint: its setup keeps the
             * records retired, and the restore's copy of record 1 is not
             * stale and goes off the list again. */
            a = entl_rec_age(&m, REC, 0);
            game_append(entl_rec_va(REC, 1), 302);
            i = entl_rec_stale(&m, REC) != 0;
            done = entl_area_sweep(&m, REC, 0, &r);
            printf(" %d %d %d %d %d %d %u", a, entl_rec_free_index(&m, REC), i, done, r.unlisted,
                   r.stale, entl_count(&m));
            /* A stage start frees them. A restore from before it (a rewind
             * across the stage start) brings back a stale copy: the cheap
             * sweep does not walk, a full one takes it off the list. */
            a = entl_rec_age(&m, REC, 1);
            printf(" %d %d", a, entl_rec_free_index(&m, REC));
            game_append(entl_rec_va(REC, 2), 303);
            i = entl_rec_stale(&m, REC) == obj_va(2);
            done = entl_area_sweep(&m, REC, 0, &r);
            printf(" %d %d %d", i, done, r.unlisted);
            done = entl_area_sweep(&m, REC, 1, &r);
            printf(" %d %d %d %d %u", done, r.unlisted, r.stale, entl_rec_stale(&m, REC) != 0,
                   entl_count(&m));
            printf(" %d %d %d\n", entl_rec_index(REC, entl_rec_va(REC, 2) + 1),
                   entl_rec_index(REC, REC - ENTL_PL_SIZE), entl_rec_index(0, REC));
        } else if (!strcmp(cmd, "unlink")) {
            /* The sweep's unlink, as sub_0004EDC0: a copy at the head, in
             * the middle, at the tail, and alone. Prints the walk's ids,
             * head and tail as node numbers, the count and the copy's
             * used byte. */
            static const int at[] = { 0, 1, 3 };
            int k;

            for (k = 0; k < 4; k++) {
                uint32_t objs[ENTL_MAX_NODES], o;
                struct entl_sweep r;
                int n, i;

                scene(k < 3 ? 4 : 1);
                o = obj_va(k < 3 ? at[k] : 0);
                g[REC + ENTL_RECORDS * ENTL_PL_SIZE] = 1;   /* record 0 used */
                w32(o + ENTL_OB_PLACEMENT, entl_rec_va(REC, 0));
                entl_rec_age(&m, REC, 0);
                printf("%s%d", k ? " | " : "", entl_area_sweep(&m, REC, 0, &r));
                n = entl_walk(&m, objs, ENTL_MAX_NODES);
                printf(" ");
                for (i = 0; i < n; i++)
                    printf("%d", entl_rd16(&m, objs[i] + ENTL_OB_ID) - 100);
                printf(" %d %d %u %d", entl_rd32(&m, ENTL_LIST) ? (int)((entl_rd32(&m, ENTL_LIST) - NODES) / 12u) : -1,
                       entl_rd32(&m, ENTL_LIST_TAIL) ? (int)((entl_rd32(&m, ENTL_LIST_TAIL) - NODES) / 12u) : -1,
                       entl_count(&m), g[o - 1]);
                /* The links back: each node's prev is the one before. */
                for (i = 1; i < n; i++)
                    if (entl_rd32(&m, NODES + 12u * (uint32_t)(objs[i] - OBJS) / OBJ_SZ) !=
                        NODES + 12u * (uint32_t)(objs[i - 1] - OBJS) / OBJ_SZ)
                        printf(" badprev");
            }
            printf("\n");
        } else if (!strcmp(cmd, "sweep")) {
            /* The safety net: a walk short of the count does nothing; a
             * marked record a listed object still points at stays held
             * until it does not; a copy spawned after the setup is not
             * the old area's. */
            struct ent_spawn_spec s;
            struct entl_plan p;
            struct entl_sweep r;
            uint32_t o, o2;
            int a, b, c;

            scene(3);
            s = from_obj(0);
            entl_spawn_check(&m, REC, 0, &s, &p);
            entl_spawn_write(&m, REC, &p, &s);
            o = game_append(p.rec_placement, 400);
            entl_rec_age(&m, REC, 0);
            w32(ENTL_LIST_COUNT, 5);
            a = entl_area_sweep(&m, REC, 0, &r);
            printf("%d %d %d %d %u %d", a, r.partial, r.unlisted, r.freed, entl_count(&m),
                   entl_rec_used(&m, REC, 0));
            w32(ENTL_LIST_COUNT, 4);
            /* On another list: the unlink would rewrite the wrong header. */
            w32(o + ENTL_OB_LIST, 0x00AF1000u);
            b = entl_area_sweep(&m, REC, 0, &r);
            printf(" %d %d %d %d %d %u", b, r.partial, r.unlisted, r.held, entl_rec_used(&m, REC, 0),
                   entl_count(&m));
            w32(o + ENTL_OB_LIST, ENTL_LIST);
            /* A spawn after the setup, before the sweep ran. */
            entl_spawn_check(&m, REC, 0, &s, &p);
            entl_spawn_write(&m, REC, &p, &s);
            o2 = game_append(p.rec_placement, 401);
            c = entl_area_sweep(&m, REC, 0, &r);
            printf(" %d %d %d %d %d%d %u %d\n", c, r.unlisted, r.freed, r.held,
                   entl_rec_used(&m, REC, 0), entl_rec_used(&m, REC, 1), entl_count(&m),
                   entl_tail(&m) == o2);
        } else if (!strcmp(cmd, "overflow")) {
            /* Spawns and retries until every record is used or retired:
             * a spawn answers ENT_RECORDS and writes nothing, the sweep
             * still bails out on a block with nothing marked or retired,
             * and the next stage start gives the retired records back. */
            struct ent_spawn_spec s;
            struct entl_plan p;
            struct entl_sweep r;
            uint8_t before[ENTL_BLOCK_SIZE];
            int i, a, b, c, d;

            scene(2);
            s = from_obj(0);
            for (i = 0; i < 100; i++) {
                entl_spawn_check(&m, REC, 0, &s, &p);
                entl_spawn_write(&m, REC, &p, &s);
            }
            entl_rec_age(&m, REC, 0);
            entl_area_sweep(&m, REC, 0, &r);
            a = r.freed;
            for (i = 0; i < 28; i++) {
                entl_spawn_check(&m, REC, 0, &s, &p);
                entl_spawn_write(&m, REC, &p, &s);
            }
            memcpy(before, g + REC, ENTL_BLOCK_SIZE);
            b = (int)entl_spawn_check(&m, REC, 0, &s, &p);
            c = !memcmp(before, g + REC, ENTL_BLOCK_SIZE);
            printf("%d %d %d %u", a, b, c, entl_count(&m));
            /* Nothing marked or retired: the sweep reads only the used
             * bytes, even with the list walk broken. */
            memset(g + REC + ENTL_RECORDS * ENTL_PL_SIZE, 1, ENTL_RECORDS);
            w32(ENTL_LIST_COUNT, 9);
            d = entl_area_sweep(&m, REC, 0, &r);
            printf(" %d %d", d, r.partial);
            w32(ENTL_LIST_COUNT, 2);
            /* Back to 100 retired, 28 used: a retry's setup marks the 28
             * and keeps the 100; a stage start frees them and a spawn
             * takes record 0. */
            memset(g + REC + ENTL_RECORDS * ENTL_PL_SIZE, 3, 100);
            memset(g + REC + ENTL_RECORDS * ENTL_PL_SIZE + 100, 1, 28);
            printf(" %d %d", entl_rec_age(&m, REC, 0), entl_rec_free_index(&m, REC));
            printf(" %d", entl_rec_age(&m, REC, 1));
            printf(" %d %d\n", (int)entl_spawn_check(&m, REC, 0, &s, &p), p.rec);
        } else if (!strcmp(cmd, "cycle")) {
            /* A list that loops back on itself: the walk stops at 64
             * nodes, short of no count the game keeps, so the sweep
             * unlinks and retires nothing. */
            struct ent_spawn_spec s;
            struct entl_plan p;
            struct entl_sweep r;
            uint32_t o;
            int a;

            scene(3);
            s = from_obj(0);
            entl_spawn_check(&m, REC, 0, &s, &p);
            entl_spawn_write(&m, REC, &p, &s);
            o = game_append(p.rec_placement, 400);
            entl_rec_age(&m, REC, 0);
            w32(entl_rd32(&m, ENTL_LIST_TAIL) + 4, entl_rd32(&m, ENTL_LIST));
            a = entl_area_sweep(&m, REC, 1, &r);
            printf("%d %d %d %d %u %d %d\n", a, r.partial, r.unlisted, r.freed, entl_count(&m),
                   g[o - 1], entl_rec_used(&m, REC, 0));
        } else if (!strcmp(cmd, "earlyout")) {
#if defined(_WIN32)
            printf("skip\n");
#else
            /* Nothing marked or retired: the cheap sweep reads the 128
             * used bytes and nothing else. The list header's page and the
             * records' pages are unreadable; a read there would fault. */
            uint8_t *keep = g;
            uint8_t *mm = mmap(NULL, MEM, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANON, -1, 0);
            uint32_t pg = (uint32_t)sysconf(_SC_PAGESIZE);
            /* The used bytes start a page (any size up to 64 KiB). */
            uint32_t used = 0x00E10000u, rec = used - ENTL_RECORDS * ENTL_PL_SIZE;
            struct entl_sweep r;
            int a;

            g = m.base = mm;
            scene(3);
            memset(g + used, 1, ENTL_RECORDS);
            mprotect(mm + (ENTL_LIST & ~(pg - 1)), pg, PROT_NONE);
            mprotect(mm + (rec & ~(pg - 1)), used - (rec & ~(pg - 1)), PROT_NONE);
            a = entl_area_sweep(&m, rec, 0, &r);
            printf("%d %d %d %d\n", a, r.partial, r.unlisted, r.freed);
            munmap(mm, MEM);
            g = m.base = keep;
#endif
        } else if (!strcmp(cmd, "took")) {
            /* After a kill: hp below the start, dead or gone took it; the
             * same hp did not. */
            struct ent_handle h;

            scene(2);
            h = entl_handle(&m, obj_va(1));
            printf("%d", entl_kill_took(&m, h, 3));
            w16(obj_va(1) + ENTL_OB_HP, 1);
            printf(" %d", entl_kill_took(&m, h, 3));
            w16(obj_va(1) + ENTL_OB_HP, 3);
            w32(obj_va(1) + ENTL_OB_STATE, ENTL_STATE_DEAD);
            printf(" %d", entl_kill_took(&m, h, 3));
            w32(obj_va(1) + ENTL_OB_STATE, 2);
            w32(NODES + 4, 0);
            w32(ENTL_LIST_COUNT, 1);
            printf(" %d\n", entl_kill_took(&m, h, 3));
        } else if (!strcmp(cmd, "contig")) {
            /* guest_alloc's block in the contiguous window, far above main
             * RAM: without the second window no record is found; with it a
             * spawn takes one, and a copy of that spawn (its placement in
             * the window) reads and copies it. A release gives a record
             * back. */
            static uint8_t hi[0x10000];
            uint32_t rec = ENTL_CONTIG_BASE + 0x100u, o;
            struct ent_spawn_spec s;
            struct entl_plan p;
            struct ent_handle h;
            int a, b, c, d;

            scene(3);
            s = from_obj(0);
            a = (int)entl_spawn_check(&m, rec, 0, &s, &p);
            m.hi = hi;
            m.hi_va = ENTL_CONTIG_BASE;
            m.hi_size = sizeof hi;
            memset(hi, 0, sizeof hi);
            b = (int)entl_spawn_check(&m, rec, 0, &s, &p);
            entl_spawn_write(&m, rec, &p, &s);
            o = game_append(p.rec_placement, 700);
            c = (int)entl_spawn_verify(&m, &p, &h);
            printf("%d %d %X %d %d", a, b, p.rec_placement, c, entl_rec_listed(&m, rec));
            s.from = h;
            d = (int)entl_spawn_check(&m, rec, 0, &s, &p);
            entl_spawn_write(&m, rec, &p, &s);
            printf(" %d %X %X %d", d, p.src_placement, p.rec_placement,
                   (int)(*(uint32_t *)(hi + (p.rec_placement - ENTL_CONTIG_BASE))));
            entl_rec_release(&m, rec, p.rec);
            printf(" %d%d %d", entl_rec_used(&m, rec, 0), entl_rec_used(&m, rec, 1),
                   entl_rec_free_index(&m, rec));
            /* The end of the window, and past it. */
            printf(" %d %d\n", entl_ok(&m, ENTL_CONTIG_BASE + sizeof hi - 4u, 4),
                   entl_ok(&m, ENTL_CONTIG_BASE + sizeof hi - 2u, 4));
            m.hi = NULL;
            m.hi_va = m.hi_size = 0;
            (void)o;
        } else if (!strcmp(cmd, "handle")) {
            /* A respawn in place keeps the handle; a slot reused by another
             * enemy (new id) or a removed one fails it. */
            struct ent_handle h;

            scene(3);
            h = entl_handle(&m, obj_va(1));
            printf("%d", entl_handle_ok(&m, h));
            w32(obj_va(1) + ENTL_OB_STATE, ENTL_STATE_DEAD);
            w32(obj_va(1) + ENTL_OB_STATE, 2);
            w16(obj_va(1) + ENTL_OB_HP, 3);
            printf(" %d", entl_handle_ok(&m, h));
            w16(obj_va(1) + ENTL_OB_ID, 999);
            printf(" %d", entl_handle_ok(&m, h));
            w16(obj_va(1) + ENTL_OB_ID, 101);
            w32(obj_va(1) + ENTL_OB_PLACEMENT, pl_va(4));
            printf(" %d", entl_handle_ok(&m, h));
            w32(obj_va(1) + ENTL_OB_PLACEMENT, pl_va(1));
            w32(NODES + 4, NODES + 24);     /* node 1 unlinked */
            printf(" %d", entl_handle_ok(&m, h));
            h.obj = 0;
            printf(" %d\n", entl_handle_ok(&m, h));
        } else if (!strcmp(cmd, "walk")) {
            /* Odd objects read field by field; a node or object outside
             * guest memory ends the walk; a cycle stops at 64 nodes. */
            uint32_t objs[ENTL_MAX_NODES];
            struct ent_info e;
            int a, b, c;

            scene(4);
            a = entl_walk(&m, objs, ENTL_MAX_NODES);
            entl_info(&m, objs[3], REC, &e);
            printf("%d %X %d %d/%d %.1f %d %d", a, objs[3], e.h.id, e.hp, e.hp_max,
                   (double)e.pos[0], e.dead, e.spawned);
            printf(" %d", entl_walk(&m, objs, 2));
            w32(NODES + 12 + 4, MEM + 0x100u);
            b = entl_walk(&m, objs, ENTL_MAX_NODES);
            w32(NODES + 12 + 4, NODES + 24);
            w32(NODES + 24 + 8, 0x10u);
            c = entl_walk(&m, objs, ENTL_MAX_NODES);
            w32(NODES + 24 + 8, obj_va(2));
            w32(NODES + 36 + 4, NODES);     /* the tail points back at the head */
            printf(" %d %d %d %X\n", b, c, entl_walk(&m, objs, ENTL_MAX_NODES), entl_tail(&m));
        } else if (!strcmp(cmd, "kill")) {
            struct ent_handle h;
            int32_t dmg;
            int a, b, c, d, e, p, s;

            scene(2);
            h = entl_handle(&m, obj_va(1));
            w16(obj_va(1) + ENTL_OB_HP, 7);
            a = (int)entl_kill_check(&m, h, 0, &dmg);
            printf("%d %d", a, dmg);
            w32(ENTL_PLAY_MODE, 0x100);
            p = (int)entl_kill_check(&m, h, 0, &dmg);
            w32(ENTL_PLAY_MODE, 0x200);
            s = (int)entl_kill_check(&m, h, 0, &dmg);
            w32(ENTL_PLAY_MODE, 0x1000);
            b = (int)entl_kill_check(&m, h, 0, &dmg);
            e = (int)entl_kill_check(&m, h, 1, &dmg);  /* the proof's any-mode kill */
            w32(ENTL_PLAY_MODE, 0);
            w32(obj_va(1) + ENTL_OB_STATE, ENTL_STATE_DEAD);
            c = (int)entl_kill_check(&m, h, 0, &dmg);
            w32(obj_va(1) + ENTL_OB_STATE, 2);
            w16(obj_va(1) + ENTL_OB_ID, 5);
            d = (int)entl_kill_check(&m, h, 0, &dmg);
            printf(" %d %d %d %d %d %d %d\n", b, c, d, dmg, e, p, s);
        } else if (!strcmp(cmd, "hp")) {
            /* Variant v's hp at 0x4AFCD8 + v * 0x20 + 0xC. */
            struct entl_hp o;
            int16_t none[4] = { -1, -1, -1, -1 }, ex[4] = { -1, 50, -1, -1 };
            uint32_t sk;
            int v;

            memset(&o, 0, sizeof o);
            scene(0);
            for (v = 1; v <= 4; v++)
                w16(ENTL_VARIANTS + (uint32_t)v * 0x20u + 0xCu, (int16_t)(v * 2));
            w16(ENTL_VARIANTS + 4u * 0x20u + 0xCu, 20000);  /* not an hp */
#define HP(v) (*(int16_t *)(g + ENTL_VARIANTS + (v) * 0x20u + 0xCu))
            sk = entl_hp_apply(&m, &o, ex, 3);
            printf("%X %d %d %d %d", sk, HP(1), HP(2), HP(3), HP(4));
            /* Again (the next area): from the saved hp, not compounded. */
            sk = entl_hp_apply(&m, &o, ex, 3);
            printf(" | %X %d %d %d %d", sk, HP(1), HP(2), HP(3), HP(4));
            sk = entl_hp_apply(&m, &o, none, 1);
            printf(" | %X %d %d %d %d %d", sk, HP(1), HP(2), HP(3), HP(4),
                   o.saved[1] + o.saved[2] + o.saved[3] + o.saved[4]);
            w16(ENTL_VARIANTS + 1u * 0x20u + 0xCu, 9000);
            entl_hp_apply(&m, &o, none, 10);
            printf(" | %d\n", HP(1));
        }
        fflush(stdout);
    }
    free(g);
    return 0;
}
"""

# ent_api.c itself, over the same fake guest and a fake mod API: the hook,
# on_frame and the guest calls are the driver's. An enemy update is the
# hook's pre call, then the game's part: a damage call made in the hook
# shows (hp 0) when the driver's damage switch says it takes. Each command
# runs in a fresh process, so ent_api.c's state starts stock.
API_MAIN = r"""
#include <stdarg.h>
#include "mod.h"
#include "ent_api.h"

size_t g_xbox_total_ram = MEM;

static xbox_mod_hook_fn s_pre;
static xbox_mod_frame_fn s_frame;
static int s_takes, s_allocs, s_ids = 500;
static uint32_t s_hit[256];
static unsigned s_nhit;
static int s_done[16], s_ndone;
static struct xbox_mod k_owner = { "entities" };

static void fake_log(const struct xbox_mod *o, const char *fmt, ...)
{
    va_list ap;

    (void)o;
    va_start(ap, fmt);
    vfprintf(stderr, fmt, ap);
    va_end(ap);
    fputc('\n', stderr);
}

static int fake_hook(uint32_t va, xbox_mod_hook_fn pre, xbox_mod_hook_fn post, uint32_t f, void *u)
{
    (void)va, (void)post, (void)f, (void)u;
    s_pre = pre;
    return 1;
}

static int fake_on_frame(xbox_mod_frame_fn fn, void *u)
{
    (void)u;
    s_frame = fn;
    return 1;
}

static uint32_t fake_alloc(const struct xbox_mod *o, uint32_t size, uint32_t align)
{
    (void)o, (void)size, (void)align;
    s_allocs++;
    return REC;
}

static int fake_call(uint32_t va, const struct xbox_guest_args *a, uint32_t *eax)
{
    (void)eax;
    if (va == 0x0004EE20u)
        game_append(a->stack[0], (int16_t)s_ids++);
    else if (va == 0x00050800u && s_nhit < 256)
        s_hit[s_nhit++] = a->stack[0];
    return 1;
}

static struct xbox_mod_api k_api;

static void update(void)
{
    struct xbox_mod_call c;
    unsigned i;

    memset(&c, 0, sizeof c);
    s_nhit = 0;
    s_pre(&c, NULL);
    for (i = 0; i < s_nhit && s_takes; i++)
        w16(s_hit[i] + ENTL_OB_HP, 0);
}

static void frame(void)
{
    s_frame(NULL);
}

static void done(enum ent_status st, struct ent_handle h, void *user)
{
    (void)h, (void)user;
    s_done[st]++;
    s_ndone++;
}

/* The game's teardown and a retry's restore: the copy goes, the checkpoint
 * brings it back (the same record, a new slot). */
static void restore(uint32_t rec_placement)
{
    game_append(rec_placement, (int16_t)s_ids++);
}

int main(void)
{
    char cmd[16];

    g = calloc(1, MEM);
    m.base = g;
    m.size = MEM;
    k_api.version = XBOX_MOD_API_VERSION;
    k_api.size = sizeof k_api;
    k_api.mem = (uintptr_t)g;
    k_api.log = fake_log;
    k_api.on_frame = fake_on_frame;
    k_api.hook = fake_hook;
    k_api.guest_call = fake_call;
    k_api.guest_alloc = fake_alloc;
    if (!ent_api_attach(&k_api, &k_owner))
        return 1;
    frame();        /* on_frame marks the guest thread */
    while (scanf("%15s", cmd) == 1) {
        if (!strcmp(cmd, "kills")) {
            /* 16 kills an update for six updates, none taking: each
             * answered once, IGNORED after four updates, never BUSY or
             * OK. Printed: the answers after each update, then all. */
            struct ent_handle h;
            int u, i;

            scene(3);
            ent_api_enable(1);
            h = entl_handle(&m, obj_va(1));
            for (u = 0; u < 6; u++) {
                for (i = 0; i < 16; i++)
                    ent_kill(h, done, NULL);
                update();
                frame();
                printf("%d ", s_ndone);
            }
            for (u = 0; u < 4; u++) {
                update();
                frame();
            }
            printf("%d %d %d %d\n", s_ndone, s_done[ENT_IGNORED], s_done[ENT_OK], s_done[ENT_BUSY]);
        } else if (!strcmp(cmd, "killwait")) {
            /* Frames without an enemy update do not age a kill (a menu
             * between two updates); 60 of them answer TIMEOUT. One that
             * took is answered at the next frame; off answers at once. */
            struct ent_handle h;
            int i, a;

            scene(3);
            ent_api_enable(1);
            h = entl_handle(&m, obj_va(1));
            ent_kill(h, done, NULL);
            update();
            for (i = 0; i < 10; i++)
                frame();
            a = s_ndone;
            for (i = 0; i < 50; i++)
                frame();
            printf("%d %d %d", a, s_ndone, s_done[ENT_TIMEOUT]);
            s_takes = 1;
            ent_kill(h, done, NULL);
            update();
            frame();
            printf(" %d", s_done[ENT_OK]);
            s_takes = 0;
            h = entl_handle(&m, obj_va(2));
            ent_kill(h, done, NULL);
            update();
            ent_api_enable(0);
            frame();
            printf(" %d %d\n", s_done[ENT_IGNORED], s_ndone);
        } else if (!strcmp(cmd, "offsweep")) {
            /* Switched off after a spawn: the retries' setups still mark
             * the record and on_frame still sweeps the restored copy; a
             * stage start frees it, and a stale copy from before it goes
             * too. Printed: count after the spawn, then after each sweep,
             * the record's used byte. */
            struct ent_spawn_spec sp;
            uint32_t rec0 = entl_rec_va(REC, 0);
#define USED(i) g[REC + ENTL_RECORDS * ENTL_PL_SIZE + (i)]
            int k;

            scene(2);
            ent_api_enable(1);
            sp = from_obj(0);
            ent_spawn(&sp, done, NULL);
            update();
            frame();
            printf("%d %u %d", s_done[ENT_OK], entl_count(&m), ent_api_spawned());
            ent_api_enable(0);
            for (k = 0; k < 2; k++) {
                /* A retry: the setup, then the restore brings the copy back. */
                ent_api_area_setup(0, 0);
                ent_api_area_setup(1, 0);
                if (k)
                    restore(rec0);
                frame();
                printf(" %u %d", entl_count(&m), USED(0));
            }
            ent_api_area_setup(0, 1);
            ent_api_area_setup(1, 1);
            restore(rec0);
            frame();
            printf(" %u %d %d\n", entl_count(&m), USED(0), s_allocs);
        } else if (!strcmp(cmd, "stock")) {
            /* Never spawned: off, or on then off, the area setups and
             * frames leave the guest's memory as it was, and nothing is
             * allocated. */
            static uint8_t before[MEM];
            int k;

            scene(3);
            memcpy(before, g, MEM);
            for (k = 0; k < 2; k++) {
                ent_api_enable(k);
                ent_api_enable(0);
                ent_api_area_setup(0, 1);
                ent_api_area_setup(1, 1);
                ent_api_area_setup(0, 0);
                ent_api_area_setup(1, 0);
                frame();
                update();
            }
            printf("%d %d\n", s_allocs, !memcmp(before, g, MEM));
        } else if (!strcmp(cmd, "typehp")) {
            /* 0 clamps to 1, past 9999 to 9999, below 0 gives the game's
             * back; variant 5 is no class-1 variant. */
            int v;

            scene(0);
            for (v = 1; v <= 4; v++)
                w16(ENTL_VARIANTS + (uint32_t)v * 0x20u + 0xCu, 2);
            ent_api_enable(1);
            printf("%d", ent_type_hp(1, 0));
            ent_type_hp(2, 20000);
            ent_type_hp(3, -5);
            printf(" %d", ent_type_hp(5, 3));
            ent_api_area_setup(0, 1);
#define HP(v) (*(int16_t *)(g + ENTL_VARIANTS + (v) * 0x20u + 0xCu))
            printf(" %d %d %d\n", HP(1), HP(2), HP(3));
        } else if (!strcmp(cmd, "nulls")) {
            /* NULL pointers answer at once. */
            struct ent_handle h;

            scene(3);
            ent_api_enable(1);
            h = entl_handle(&m, obj_va(1));
            printf("%d %d %d %d\n", ent_spawn(NULL, done, NULL), ent_list(NULL, 4),
                   ent_list(NULL, 0), ent_read(h, NULL));
        }
        fflush(stdout);
    }
    free(g);
    return 0;
}
"""


def _toolkit_includes():
    """The toolkit's header directories (external/xboxrecomp or
    ../xboxrecomp, as CMakeLists.txt finds it), or None."""
    for d in (os.path.join(ROOT, "external", "xboxrecomp"), os.path.join(ROOT, "..", "xboxrecomp")):
        if os.path.exists(os.path.join(d, "src", "enhance", "mod.h")):
            dirs = set()
            for sub in ("src", "include"):
                for dp, _, fs in os.walk(os.path.join(d, sub)):
                    if any(f.endswith(".h") for f in fs):
                        dirs.add(dp)
            return sorted(dirs) + [os.path.join(d, "src"), os.path.join(d, "include")]
    return None


@pytest.fixture(scope="module")
def api():
    cc = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    inc = _toolkit_includes()
    if not cc or not inc:
        pytest.skip("no C compiler or no toolkit beside the project")
    d = tempfile.mkdtemp()
    c = os.path.join(d, "api.c")
    exe = os.path.join(d, "api")
    with open(c, "w") as f:
        f.write(DRIVER[: DRIVER.index("int main(void)")] + API_MAIN)
    subprocess.run(
        [cc, "-std=c11", "-Wall", "-Werror", "-Wno-unused-function", "-Wno-comment"]
        + ["-DRECOMP_ENV_HAVE_ENHANCE_KEYS", "-I", SRC]
        + [x for i in inc for x in ("-I", i)]
        + [c, os.path.join(SRC, "ent_api.c"), os.path.join(SRC, "ent_api_logic.c"), "-o", exe],
        check=True,
    )

    def run(cmd):
        out = subprocess.run([exe], input=cmd + "\n", capture_output=True, text=True, check=True)
        return out.stdout.strip()

    yield run
    shutil.rmtree(d)


@pytest.fixture(scope="module")
def drv():
    cc = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    if not cc:
        pytest.skip("no C compiler")
    d = tempfile.mkdtemp()
    c = os.path.join(d, "drv.c")
    exe = os.path.join(d, "drv")
    with open(c, "w") as f:
        f.write(DRIVER)
    subprocess.run(
        [
            cc,
            "-std=c11",
            "-Wall",
            "-Werror",
            "-I",
            SRC,
            c,
            os.path.join(SRC, "ent_api_logic.c"),
            "-o",
            exe,
        ],
        check=True,
    )

    def run(cmd):
        out = subprocess.run([exe], input=cmd + "\n", capture_output=True, text=True, check=True)
        return out.stdout.strip()

    yield run
    shutil.rmtree(d)


def _st(line):
    return [STATUS[int(x)] for x in line.split()]


def test_guards_in_order(drv):
    # Leaked, play mode, VS (with play mode back to 0), a stale handle, a
    # class off the list, the cap, no record, then OK.
    assert _st(drv("guards")) == [
        "LEAK",
        "TIME_CONTROL",
        "TIME_CONTROL",
        "MODE",
        "GONE",
        "CLASS",
        "CAP",
        "RECORDS",
        "OK",
    ]


def test_cap_keeps_no_reserve(drv):
    # The audit found no unchecked mid-stage spawn left on the allowlist, so
    # the 34th slot is the API's to take.
    assert _st(drv("cap")) == ["OK", "CAP"]


def test_spawn_from_the_stage_table(drv):
    st, va, *rest = drv("table").split()
    assert STATUS[int(st)] == "OK"
    assert int(va, 16) == 0x466000 + 0x5C
    assert [STATUS[int(x)] for x in rest] == ["GONE", "GONE", "GONE"]


def test_allowlist(drv):
    # Every class the stage tables and extra sets spawn, less the spawner
    # 0x14 and the extra sets' 0x21; the class byte only (& 0xFF).
    base = [0x01, 0x02, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0A, 0x0D, 0x0E, 0x10, 0x12]
    base += list(range(0x81, 0x87))
    want = base + [c + 0x100 for c in base]
    assert [int(x, 16) for x in drv("allowed").split()] == want


def test_placement_copy_and_respawn_nibble(drv):
    recs, a, b, mode2, used = [p.split() for p in drv("write").split("|")]
    # Three records in order, none reused.
    assert [int(x, 16) for x in recs] == [0, 0x5C, 0xB8]
    # The spec's position and rot_y; never respawns: top nibble 2, the
    # crystal colours in the low bits kept.
    assert a == ["1", "40.00", "50.00", "60.00", "1.25", "20ABCDEF"]
    # No position given: the source enemy's (enemy 2 at 3, 2, 3); rot_y the
    # placement's.
    assert b == ["3.00", "2.00", "3.00", "0.50", "20ABCDEF"]
    # ENT_RESPAWN_KEEP: the source's mode.
    assert mode2 == ["10ABCDEF"]
    assert used == ["1110"]


def test_verify(drv):
    before, after, same_obj, same_pl, ident, wrong_tail = drv("verify").split()
    assert STATUS[int(before)] == "LEAK"
    assert STATUS[int(after)] == "OK"
    assert (same_obj, same_pl, ident) == ("1", "1", "555")
    assert STATUS[int(wrong_tail)] == "LEAK"


def test_records_free_at_stage_start(drv):
    out = drv("records").split()
    nxt, listed, stale = out[:3]
    aged, done, unlisted, freed, used, nxt2, count = out[3:10]
    rew_stale, rew_done, rew_unlisted, rew_freed, rew_count = out[10:15]
    aged2, nxt3, stale2, done2, unlisted2, stale_n2, count2 = out[15:22]
    aged3, nxt4, stale3, cheap_done, cheap_unlisted = out[22:27]
    full_done, full_unlisted, full_stale, stale_after, count3 = out[27:32]
    mis, below, noblock = out[32:]
    # Three spawns took records 0-2, one enemy points at record 1: the next
    # free one is 3 (none reused within the stage), nothing stale.
    assert (nxt, listed, stale) == ("3", "1", "0")
    # A retry's setup marks all three; the next enemy update takes record
    # 1's copy off the list (the checkpoint restore brought it back, design
    # D5) and retires all three: still not free, 3 is the next.
    assert (aged, done, unlisted, freed) == ("3", "1", "1", "3")
    assert (used, nxt2, count) == ("111", "3", "2")
    # A rewind brings back an enemy of the retired record 2: not stale, and
    # the next sweep takes it off the list again (open question 3).
    assert (rew_stale, rew_done, rew_unlisted, rew_freed, rew_count) == ("0", "1", "1", "0", "2")
    # A second retry from the same checkpoint (review): its setup
    # frees nothing, so the restored copy of record 1 is a retired record's
    # again, not stale, and goes off the list.
    assert (aged2, nxt3, stale2) == ("0", "3", "0")
    assert (done2, unlisted2, stale_n2, count2) == ("1", "1", "0", "2")
    # A stage start frees them. A restore from before it leaves a stale
    # copy: the cheap sweep (nothing marked or retired) does not walk; the
    # full one, asked for when on_frame sees the copy, takes it off.
    assert (aged3, nxt4, stale3, cheap_done, cheap_unlisted) == ("0", "0", "1", "1", "0")
    assert (full_done, full_unlisted, full_stale, stale_after, count3) == ("1", "1", "1", "0", "2")
    # A misaligned va, one below the block, no block: no record.
    assert (mis, below, noblock) == ("-1", "-1", "-1")


def test_area_sweep_unlinks_as_the_game_does(drv):
    # A copy at the head, in the middle, at the tail, and alone: off the
    # walk, head and tail fixed, count one less, its pool slot free, the
    # other nodes' prev links intact.
    head, mid, tail, alone = [p.split() for p in drv("unlink").split("|")]
    assert head == ["1", "123", "1", "3", "3", "0"]
    assert mid == ["1", "023", "0", "3", "3", "0"]
    assert tail == ["1", "012", "0", "2", "3", "0"]
    # Alone (head == tail): an empty walk, head and tail 0.
    assert alone == ["1", "-1", "-1", "0", "0"]


def test_area_sweep_safety_net(drv):
    out = drv("sweep").split()
    # A walk short of the count (4 of 5): nothing unlinked or freed.
    assert out[:6] == ["0", "1", "0", "0", "5", "1"]
    # A copy whose object names another list header: not unlinked, so its
    # record is held (still used), tried again next frame.
    assert out[6:12] == ["0", "0", "0", "1", "1", "4"]
    # Back on this list: unlinked and retired (not free until the next
    # setup); a copy spawned after the setup (record 1) stays listed and used.
    assert out[12:] == ["1", "1", "1", "0", "11", "4", "1"]


def test_record_overflow(drv):
    out = drv("overflow").split()
    retired, status, untouched, count, done, partial = out[:6]
    retry_marked, retry_next, marked, again, rec = out[6:]
    # 100 retired by a retry, 28 more used: the next spawn answers RECORDS
    # and leaves the block and the list as they were.
    assert (retired, STATUS[int(status)], untouched, count) == ("100", "RECORDS", "1", "2")
    # Nothing marked or retired: done without a walk (no partial).
    assert (done, partial) == ("1", "0")
    # A retry's setup marks the 28 and keeps the 100 retired: still none
    # free. A stage start frees the 100 (the 28 stay marked); spawns resume.
    assert (retry_marked, retry_next) == ("28", "-1")
    assert (marked, STATUS[int(again)], rec) == ("28", "OK", "0")


def test_area_sweep_stops_on_a_cycle(drv):
    # A looped list (review): partial, nothing unlinked or retired,
    # the copy's slot and its record still in use.
    assert drv("cycle").split() == ["0", "1", "0", "0", "4", "1", "1"]


def test_area_sweep_early_out_reads_only_the_used_bytes(drv):
    # Nothing marked or retired, the list header and the records unreadable:
    # done, no walk.
    out = drv("earlyout")
    if out == "skip":
        pytest.skip("no mprotect")
    assert out.split() == ["1", "0", "0", "0"]


def test_kill_took(drv):
    # Same hp: ignored; lower hp, dead or gone: taken.
    assert drv("took").split() == ["0", "1", "1", "1"]


def test_records_in_the_contiguous_window(drv):
    no_win, ok, rec, verified, listed, copy, src, rec2, cls, used, nxt, end, past = drv(
        "contig"
    ).split()
    # The block guest_alloc gives sits at 0x80000000 up: outside main RAM
    # alone there is no record (the bug the window fixes).
    assert STATUS[int(no_win)] == "RECORDS"
    assert STATUS[int(ok)] == "OK"
    assert int(rec, 16) == 0x80000100
    assert (STATUS[int(verified)], listed) == ("OK", "1")
    # A copy of the API's own spawn: its placement is a record in the window.
    assert STATUS[int(copy)] == "OK"
    assert (int(src, 16), int(rec2, 16), cls) == (0x80000100, 0x80000100 + 0x5C, "1")
    # Released: record 1 free again, record 0 still held.
    assert (used, nxt) == ("10", "1")
    assert (end, past) == ("1", "0")


def test_handle_across_respawn_and_reuse(drv):
    # Same enemy dead then back: valid; another id or placement in the slot,
    # or off the list: gone; no object: gone.
    assert drv("handle").split() == ["1", "1", "0", "0", "0", "0"]


def test_walk(drv):
    n, obj, ident, hp, x, dead, spawned, capped, broken, badobj, cycle, tail = drv("walk").split()
    assert n == "4"
    assert int(obj, 16) % 2 == 1
    assert (ident, hp, x, dead, spawned) == ("103", "3/3", "4.0", "0", "0")
    assert capped == "2"
    # Node 1's next outside memory: two objects; node 2's object below the
    # first page: two; a cycle: 64.
    assert (broken, badobj, cycle) == ("2", "2", "64")
    assert int(tail, 16) % 2 == 1


def test_kill_guards(drv):
    ok, dmg, tc, dead, gone, dmg_after, any_mode, pause, slow = drv("kill").split()
    assert (STATUS[int(ok)], dmg) == ("OK", "7")
    # REW refuses; PAUSE and SLOW let a kill through (open question 1).
    assert [STATUS[int(x)] for x in (tc, dead, gone)] == ["TIME_CONTROL", "DEAD", "GONE"]
    assert [STATUS[int(x)] for x in (pause, slow)] == ["OK", "OK"]
    assert dmg_after == "0"
    # The proof's switch lets a kill through any mode, REW included.
    assert STATUS[int(any_mode)] == "OK"


def test_hp_override_apply_and_restore(drv):
    first, again, restored, clamped = [p.split() for p in drv("hp").split("|")]
    # Variant 4 holds no plausible hp (20000): skipped (bit 4), untouched.
    # Variant 2 explicit 50; 1 and 3 times 3.
    assert first == ["10", "6", "50", "18", "20000"]
    assert again == first
    # Back to the game's; nothing saved after.
    assert restored == ["0", "2", "4", "6", "20000", "0"]
    # 9000 times 10 clamps to a short.
    assert clamped == ["32767"]


def test_api_kills_answer_once(api):
    # the tracker item review: the pending kills hold every kill in flight. Six
    # updates of 16 kills that never take: none answered before four
    # updates, then 16 an update; 96 IGNORED in all, none OK or BUSY.
    assert api("kills").split() == ["0", "0", "0", "0", "16", "32", "96", "96", "0", "0"]


def test_api_kill_waits_count_updates(api):
    # Ten frames with no enemy update: not answered (updates, not frames);
    # 60: TIMEOUT. A hit that took: OK at the next frame. Switched off with
    # a kill pending: IGNORED.
    assert api("killwait").split() == ["0", "1", "1", "1", "1", "3"]


def test_api_off_after_a_spawn_keeps_sweeping(api):
    # Spawned (count 3, one listed copy), then off. Two retries: the setup
    # marks the record and the frame's sweep takes the copy off (the first
    # retry's copy is the one still listed, the second's a restore), the
    # record retired (3). The stage start frees it (0) and the stale copy a
    # restore from before it brings back goes too. One block, never more.
    assert api("offsweep").split() == ["1", "3", "1", "2", "3", "2", "3", "2", "0", "1"]


def test_api_never_spawned_stays_stock(api):
    assert api("stock").split() == ["0", "1"]


def test_api_type_hp_clamps(api):
    ok, cls, hp1, hp2, hp3 = api("typehp").split()
    assert (STATUS[int(ok)], STATUS[int(cls)]) == ("OK", "CLASS")
    assert (hp1, hp2, hp3) == ("1", "9999", "2")


def test_api_null_pointers(api):
    spawn, lst, lst0, read = api("nulls").split()
    assert STATUS[int(spawn)] == "GONE"
    assert (lst, lst0, read) == ("-1", "0", "-1")


def _read(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as f:
        return f.read()


def test_env_rows():
    text = _read("src", "env", "recomp_env_game.h")
    for name, (env, _) in SETTINGS.items():
        m = re.search(r'X\(\w+,\s*CONFIG,\s*"' + env + r'",\s*NULL,\s*"([^"]*)"', text)
        assert m, f"{env}: no CONFIG row in recomp_env_game.h"
        assert f"mods.entities.{name}" in m.group(1), f"{env}: its row does not name the key"
    for cid, env in CONTROLS.items():
        m = re.search(r'X\(\w+,\s*CONFIG,\s*"' + env + r'",\s*NULL,\s*"([^"]*)"', text)
        assert m and f"entities.{cid}" in m.group(1), env
    assert re.search(r'X\(ENTITIES_PROOF,\s*DEBUG,\s*"entities_proof"', text)


def test_env_doc_has_every_key():
    doc = _read("docs", "env.md")
    for name, (env, _) in SETTINGS.items():
        assert f"| `{env}` | `{env}`" in doc, f"{env}: no docs/env.md row"
        assert f'`mods."entities.{name}"`' in doc, f"entities.{name}: not in docs/env.md"
    for env in CONTROLS.values():
        assert f"| `{env}` | `{env}`" in doc
    assert "| (none) | `entities_proof` |" in doc


def test_descriptor_declares_each_setting_and_control():
    text = _read("src", "entities_mod.c")
    for name, (env, kind) in SETTINGS.items():
        m = re.search(r'\{ "' + name + r'", NULL, "' + env + r'".*?\}', text, re.S)
        assert m, f"{name}: no descriptor row with env {env}"
        assert kind in m.group(0), f"{name}: not {kind}"
    assert "XBOX_SET_ENABLE" in re.search(r'\{ "enable".*?\}', text, re.S).group(0)
    for cid, env in CONTROLS.items():
        assert re.search(
            r'\{ "' + cid + r'",.*?XBOX_CTL_ACTION, NULL, NULL, "' + env + '"', text, re.S
        ), cid
    assert '{ "entities", init, NULL, &k_desc' in text
    assert 'actions_arm("mods.entities.enable")' in text


def test_golden_knows_the_stock_value():
    with open(os.path.join(ROOT, "game.toml"), "rb") as f:
        stock = tomllib.load(f)["golden"]["enhance_stock"]
    assert stock.get("mods.entities.enable") == "off"


def test_hook_slot_and_area_setup_wrapper():
    with open(os.path.join(ROOT, "game.toml"), "rb") as f:
        mods = tomllib.load(f)["mods"]
    assert "0x0004E700" in mods["hook_functions"]
    assert "0x0004E700" in mods.get("no_st0", [])
    # stage_area_setup belongs to recomp_manual.c, so it is no hook slot.
    assert "0x000606F0" not in mods["hook_functions"]
    with open(os.path.join(ROOT, "config", "hook_functions.json"), encoding="utf-8") as f:
        assert "0x0004E700" in json.load(f)["mods"]["hook_functions"]
    body = re.search(
        r"void sub_000606F0\(void\)\n\{(.*?)\n\}", _read("src", "recomp_manual.c"), re.S
    )
    assert body
    lines = [ln.strip() for ln in body.group(1).strip().splitlines()]
    i = lines.index("RECOMP_ABI_CALL(0x000606F0u, sub_000606F0_gen);")
    assert "ent_api_area_setup(0, stage_start);" in lines[:i]
    assert lines[i + 1] == "ent_api_area_setup(1, stage_start);"
    # A stage start, told by the caller's return address, not a retry.
    assert "int stage_start = MEM32(g_esp) == ENTL_SETUP_STAGE_START;" in lines[:i]
    assert re.search(
        r"#define ENTL_SETUP_STAGE_START\s+0x0006324Du", _read("src", "ent_api_logic.h")
    )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
