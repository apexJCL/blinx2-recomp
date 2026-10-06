/*
 * unimpl_budget.h - which [UNIMPL] hits get a log line.
 *
 * recomp_unimpl used to print the first 50 hits in the whole run. One chatty
 * site spent all of them: 48 lines of `in al,dx` hid D3DX's MMX probe
 * (pushfd/popfd/cpuid in sub_00301AB1) for weeks. So the budget is per
 * address now: the first `per_addr` hits of each site print, then hits 10,
 * 100, 1000 ... of it, which says the site is in a loop without flooding.
 *
 * Sites are kept in a fixed open-addressed table, lock-free because guest
 * threads hit these concurrently. A run reaches a few dozen sites at most;
 * the table holds UNIMPL_SLOTS. If it ever fills, a hit at an untracked
 * address prints anyway, up to UNIMPL_OVERFLOW_LINES, so a new site is not
 * silenced by the table either.
 *
 * Header-only so scripts/test_unimpl_budget.py can compile it alone.
 */
#ifndef CAT_UNIMPL_BUDGET_H
#define CAT_UNIMPL_BUDGET_H

#include <stdatomic.h>
#include <stdint.h>

enum { UNIMPL_SLOTS = 1024, UNIMPL_OVERFLOW_LINES = 200 };

struct unimpl_budget {
    _Atomic uint32_t key[UNIMPL_SLOTS];   /* va + 1; 0 is a free slot */
    _Atomic uint32_t hits[UNIMPL_SLOTS];
    _Atomic uint32_t overflow;
};

/* Count a hit at `va`. Returns the site's hit number when this hit should be
 * printed, 0 when it should not. The first hit of a site always prints:
 * per_addr below 1 counts as 1. A table-full hit (or va 0xFFFFFFFF, which
 * has no key) returns UINT32_MAX while the overflow lines last. */
static inline uint32_t unimpl_budget_hit(struct unimpl_budget *b, uint32_t va,
                                         long per_addr)
{
    uint32_t key = va + 1u, n, m, k;
    uint32_t slot = (uint32_t)(va * 2654435761u) % UNIMPL_SLOTS;

    if (per_addr < 1)
        per_addr = 1;
    /* 0xFFFFFFFF would key as 0, a free slot: give it the overflow path. */
    for (k = key ? 0 : UNIMPL_SLOTS; k < UNIMPL_SLOTS; k++, slot = (slot + 1) % UNIMPL_SLOTS) {
        uint32_t cur = atomic_load_explicit(&b->key[slot], memory_order_acquire);
        if (cur == 0) {
            uint32_t empty = 0;
            if (atomic_compare_exchange_strong(&b->key[slot], &empty, key))
                cur = key;
            else
                cur = empty;        /* another thread claimed it; for this va? */
        }
        if (cur != key)
            continue;
        n = atomic_fetch_add(&b->hits[slot], 1u) + 1u;
        if (n <= (uint32_t)per_addr)
            return n;
        for (m = n; m >= 10 && m % 10 == 0; m /= 10)
            ;
        return m == 1 ? n : 0;
    }
    n = atomic_fetch_add(&b->overflow, 1u) + 1u;
    return n <= UNIMPL_OVERFLOW_LINES ? UINT32_MAX : 0;
}

#endif /* CAT_UNIMPL_BUDGET_H */
