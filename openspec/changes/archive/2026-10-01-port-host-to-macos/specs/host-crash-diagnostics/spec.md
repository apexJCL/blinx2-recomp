## Purpose

Defines what the host reports when recompiled guest code faults, so that a crash on any supported host points to the guest function and call chain responsible. This is the main signal for the build → crash → fix loop.

## ADDED Requirements

### Requirement: Fault report contents
When guest code causes a memory access fault that isn't otherwise serviced, the host SHALL write a fault report to stderr before the process terminates. The report SHALL contain:
- the host faulting address and the faulting data address
- whether the access was a read or a write, when the host can tell
- the fault's guest virtual address (data address minus the guest memory offset)
- the guest registers eax, ebx, ecx, edx, esi, edi and esp

The report SHALL be flushed before the process terminates.

#### Scenario: Null-page write in guest code on macOS
- **WHEN** a recompiled function writes to an unmapped guest address on macOS arm64
- **THEN** stderr contains a `[CRASH]` line with the host and data fault addresses, a line with the guest VA, and the seven guest register values

#### Scenario: Same report on Windows
- **WHEN** the same fault happens on Windows x64
- **THEN** the report has the same fields, labels and order as on macOS

### Requirement: Guest function name
The report SHALL name the host symbol containing the faulting instruction (normally a generated `sub_XXXXXXXX` function) and the offset into it, whenever the host can resolve one. When it can't, the report SHALL say the symbol is unknown rather than omitting the line.

#### Scenario: Fault inside a generated function
- **WHEN** a fault happens inside generated function `sub_00012000`
- **THEN** the report contains `in sub_00012000+0x` followed by a hexadecimal offset

### Requirement: Guest call chain
The report SHALL list up to 24 candidate guest return addresses, innermost first. These are values on the guest stack, scanned up from guest esp, that fall inside the guest code range. When no candidate is found, the report SHALL say so explicitly. It SHALL then print the 16 most recent indirect-call (ICALL) targets and the first 20 raw words of the guest stack.

#### Scenario: Chain recovered
- **WHEN** the guest stack holds return addresses into guest code
- **THEN** the report lists them with their esp offsets and doesn't print the raw stack dump

#### Scenario: Chain destroyed
- **WHEN** no guest stack word within the scanned window falls inside guest code
- **THEN** the report prints `(no return addresses in range)`, the recent ICALL targets, and the raw stack words

#### Scenario: Guest esp outside guest RAM
- **WHEN** the fault happens while guest esp is outside guest RAM, or so close to its end that the scanned window would extend past it
- **THEN** the report doesn't read the guest stack. It prints `(no return addresses in range)` with a note that esp is outside guest RAM, and the recent ICALL targets, without faulting again

### Requirement: Diagnostics must not mask the fault
The fault handler SHALL NOT turn an unserviced fault into a silent hang or a successful exit. After reporting, the process SHALL terminate abnormally: on POSIX hosts, with the original signal's default disposition, so that the exit status and any core dump reflect it. A fault that happens while a report is being written SHALL terminate the process rather than recurse.

#### Scenario: Exit status after a crash on macOS
- **WHEN** the guest faults and the report has been written
- **THEN** the process terminates by `SIGSEGV` or `SIGBUS`, and the shell reports a signal exit, not 0

#### Scenario: Fault during reporting
- **WHEN** reading the guest stack during a report itself faults
- **THEN** the process terminates without printing the report again

### Requirement: Crash handling covers every thread
Crash diagnostics SHALL apply to faults on any thread running guest code, including threads the guest creates through the kernel. On the boot thread, they SHALL also keep working when the stack is exhausted. On guest-created threads, stack exhaustion MAY end the process without a report until the toolkit offers a thread-start hook. In that case the process SHALL still terminate by signal and SHALL NOT exit 0.

#### Scenario: Fault on a guest-created thread
- **WHEN** a thread created by the guest faults with stack to spare
- **THEN** a fault report is written, with that thread's guest registers

#### Scenario: Stack overflow on the boot thread
- **WHEN** runaway recursion in generated code exhausts the boot thread's stack
- **THEN** a fault report is still written instead of the process dying silently
