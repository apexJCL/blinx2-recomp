## ADDED Requirements

### Requirement: A stride-0 vertex array is an array
A vertex attribute whose SET_VERTEX_DATA_ARRAY_FORMAT size is non-zero SHALL be read from memory on every backend (CPU, Metal, D3D11), whatever its stride. At stride 0 every vertex of the draw SHALL read the one element at the attribute's offset. Only an attribute with size 0 SHALL read its SET_VERTEX_DATA (inline) value.

#### Scenario: Per-batch constant in an array
- **WHEN** attribute 4 is float, size 3, stride 0, at an offset holding (0, 1, 0), the inline v4 is (1, 0, 0, 1), and a program writes v4 to oD0
- **THEN** every vertex reads (0, 1, 0, 1) and the quad draws opaque green

#### Scenario: Disabled attribute
- **WHEN** the same attribute has size 0
- **THEN** every vertex reads the inline value (1, 0, 0, 1)
