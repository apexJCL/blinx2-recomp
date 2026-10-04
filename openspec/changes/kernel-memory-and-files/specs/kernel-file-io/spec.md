## ADDED Requirements

### Requirement: Open files can be renamed
NtSetInformationFile with FileRenameInformation (class 10) SHALL rename the open file. The target SHALL be resolved relative to RootDirectory when set, within the file's own directory for a bare name, and through the Xbox path table otherwise. An existing target SHALL be replaced only when ReplaceIfExists is set; otherwise the call SHALL fail with STATUS_OBJECT_NAME_COLLISION.

#### Scenario: Utility-drive texture cache
- **WHEN** BLiNX 2 writes `z:\media\plcom_tex.tmp` and renames it to `plcom_tex.ipk`
- **THEN** the rename succeeds, no `unhandled class 10` line is logged, and the next open of the `.ipk` succeeds

### Requirement: An overwrite open keeps the data a regrow exposes
An overwrite open (FILE_SUPERSEDE, FILE_OVERWRITE or FILE_OVERWRITE_IF) of an existing file SHALL behave as FATX does. If the handle's first operation sets the end of file, the bytes below the new end SHALL keep their old contents. If its first operation is a read, a write, a size query, an allocation or a close, the file SHALL be empty first.

#### Scenario: Texture-cache trim
- **WHEN** BLiNX 2 writes `z:\lng_us\title_tex_us.tmp` padded to 512 bytes, reopens it with CREATE_ALWAYS, sets the end of file to the true size and renames it to `.ipk`
- **THEN** the `.ipk` holds the written data (it starts with `IPK1`), not zeros
