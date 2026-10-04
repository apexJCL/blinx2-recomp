## ADDED Requirements

### Requirement: Toolkit structures never overlap the title image
The toolkit SHALL place its guest-visible structures (scratch region with kernel data exports and fake TIB/TLS data, main stack, heap) at or above the first 64 KB boundary past the end of the highest loaded XBE section, and never below guest VA 0x00700000.

#### Scenario: Large image
- **WHEN** a title whose sections end at 0x0303AC20 boots
- **THEN** the scratch region starts at 0x03040000, the main stack and heap lie above it, and no heap allocation, thread stack or toolkit structure overlaps a loaded section

#### Scenario: Small image keeps today's addresses
- **WHEN** a title whose sections end below 0x00700000 boots
- **THEN** kernel data is at 0x00740000, the main stack is 8 MB at 0x00780000, and the heap starts at 0x00F80000, exactly as before

### Requirement: Every XBE section is loaded
The loader SHALL copy every section listed in the XBE header that lies within guest RAM, whatever the section count.

#### Scenario: More than 64 sections
- **WHEN** an XBE with 73 sections boots
- **THEN** the boot log reports 73 sections loaded

### Requirement: Layout that does not fit fails at boot
When the title image leaves too little RAM for at least a 1 MB main stack and a 1 MB heap, memory layout initialization SHALL fail with an error naming the image end and the RAM size, instead of starting the title.

#### Scenario: Image too large
- **WHEN** the image ends within 2 MB of the end of mapped RAM
- **THEN** the host reports a fatal memory-layout error and exits non-zero without running guest code
