## D1. The rule, and xemu as the reference

`SET_VERTEX_DATA_ARRAY_FORMAT(i)` (0x1760 + 4i) carries the type in bits [3:0], the size (component count) in [7:4] and the stride in [31:8]. The rule:

| size | stride | what each vertex reads |
|---|---|---|
| 0 | any | the SET_VERTEX_DATA value (inline) |
| > 0 | 0 | the one element at `offset` |
| > 0 | > 0 | the element at `offset + index * stride` |

The reference is xemu, read at master f78d85e and not run:

- **`hw/xbox/nv2a/pgraph/pgraph.c`, `DEF_METHOD_INC(NV097, SET_VERTEX_DATA_ARRAY_FORMAT)`:** stores `format`, `count` (the size field) and `stride`.
- **`hw/xbox/nv2a/pgraph/gl/vertex.c`, `pgraph_gl_bind_vertex_attributes()`:**
  - `if (!attr->count)`: disables the array and binds `attr->inline_value`.
  - Otherwise the data address is `offset + min_element * stride`, which is the offset itself when the stride is 0. Then:

    ```c
    if (!stride) {
        // Stride of 0 indicates that only the first element should be
        // used.
        pgraph_update_inline_value(attr, last_entry);
        glDisableVertexAttribArray(i);
        glVertexAttrib4fv(i, attr->inline_value);
        continue;
    }
    ```

    The element at the offset becomes a constant attribute for the whole draw.
- **`hw/xbox/nv2a/pgraph/vk/vertex.c`, `pgraph_vk_bind_vertex_attributes()`:** the same two branches (`!attr->count`, then `!stride`), through its uniform attributes.

The toolkit tested `size && stride`, so the middle row read the inline value.

The toolkit decodes only bits [15:8] of the stride (`(param >> 8) & 0xFF`); xemu takes [31:8]. A stride of 256 or more would now decode as a stride-0 array rather than the inline value. Titles seen so far stay under 256, so widening the mask is a follow-up (D4), not part of this change.

## D2. 86AE0156 and the snow tint

With the fix, SSX 3's program 86AE0156 changes from attribute mask 0007 to FF87. Its v7 and v8–v15 are stride-0 arrays. Before, they read inline values; now they read the elements, as xemu does under D1. The new output is what the hardware rule gives, not a side effect to undo.

An earlier draft blamed this program for a pink or cream tint on the snow. That was inferred without a matching "before" run: run35 stopped at flip 5900, before the tinted stretch of the course. Run42 (the old rule, the same save, pad script and frames as run41) shows the pink and orange snow too, and stronger: it fills the frame at flips 6300 and 6400, where run41 shows mostly blue snow with coloured streaks. So the tint predates this change and is not caused by it. If it is wrong, the cause is elsewhere (the combiner, blending or fog), and that is a separate item. The pair is `runs/ssx3/snow-ab-ITEM.jpg`. The two runs diverge (3rd vs 6th place), so the frames pair the stretch of course, not the exact view.

## D3. Per backend

- **CPU** (`nv2a_pb_exec.c`):
  - `vsh_inputs()` tests `at->size` and the offset (or an active inline array).
  - In `fetch_attr()`, `offset + index * stride` already gives the offset for every index at stride 0. The test that refused stride 0 is gone.
  - Inline arrays (INLINE_ARRAY) set their own strides, so they're unaffected.
  - The `batches_no_uv` statistic still counts `offset && stride`; it is only a statistic.
  - The fixed-function helpers `color_attr()` and `texcoord_attr()` still pick the first attribute with a stride, so a stride-0 diffuse or texcoord array is passed over for another array. This is CPU-only, and a follow-up (D4).
- **Metal** (`metal_on_draw`): each input is expanded per vertex through `fetch()`, which already reads `offset + index * stride`. The `on` test becomes `size != 0`.
- **D3D11** (`d3d11_on_draw`):
  - Inputs in a format the input assembler reads natively, and per-vertex float4 inputs, still need a stride (`size && stride`). A stride-0 array in those formats is not handed to the input assembler at stride 0. It falls to the third branch: one float4 at stride 0.
  - That float4 is now `fetch(d, a, 0, f)` when the attribute has a size, and the inline value only when the size is 0 or the fetch fails. The input layout then repeats it for every vertex, as xemu does.
  - The `bound` estimate already allows 32 bytes for that case (one float4 plus alignment).
  - The `trace_batch` dumps (vsh trace at 2602 and 2618) take the same `!a->size` test.

## D4. Out of scope (follow-ups)

- **xemu's inline-value update:** after binding an array, xemu copies the provoking vertex's element (or the stride-0 element) into `inline_value`. A later draw with that attribute disabled then reads the last array value, not the last SET_VERTEX_DATA. The toolkit doesn't do this. A first try, which kept the last fetched v4 (run36, `vsh_inl_last`), broke the rider's body from flip 4600. A correct port needs the provoking-vertex rule per primitive type, so it gets its own item.
- **Burnout 3:** goldens on Metal and D3D11 under the new rule.
- **Stride width:** decode the stride from bits [31:8] as xemu does (D1).
- **CPU fixed-function helpers:** `color_attr()` and `texcoord_attr()` follow the new rule (D3).

## D5. Evidence

- **Runs** (`runs/ssx3/`, Metal, run24 save and pad script):
  - run35 (probe): the body goes off screen from flip 5620, when 8F706D7F starts writing inline v4.
  - run39 (fix, flips 4600–5900): the body is on screen throughout. 8F706D7F first draws at 5938.
  - run40 (fix, 5800–6800): 8F706D7F draws from 5653 and the body stays on screen. `ab.jpg` pairs run35 f5700 with run40 f5900.
- **Trace:** run37's `[VSH-V4]` log shows inline v4 written only by method 0x1950 (= 0) at flip 0 and by 8F706D7F's 0x1A40..0x1A4C.
- **Format:** run38 shows attr 4 for D94C1234 as type 2, size 3, stride 0, one offset per mesh.
