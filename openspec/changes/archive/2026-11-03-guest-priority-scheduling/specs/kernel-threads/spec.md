## ADDED Requirements

### Requirement: Guest priorities order the guest CPU
With the guest CPU lock on and `RECOMP_DEBUG=guest_sched=1`, the runtime SHALL keep each guest thread's base priority, normalised as NT does, and `KeQueryBasePriorityThread` SHALL return the stored value. A release of the guest CPU SHALL go to the highest-priority waiter that is not suspended, the oldest first among equals. A holder whose priority is above every waiter's SHALL keep the guest CPU at the quantum, at back edges, at spin-wait passes and at `NtYieldExecution`. A kernel call's soft release SHALL go to a lower-priority waiter only when the caller blocks (a wait only once it finds its object unsignalled) or after 2 ms. A waiter kept off the guest CPU for 4 s SHALL get one turn at the holder's next hand-off, reserved against other takers, and a logged line (a hang guard; a golden wants 0 firings). With the key off, the guest CPU SHALL behave as before.

#### Scenario: Time-critical lock
- **WHEN** a thread raises itself to priority 15 and others at normal priority wait for the guest CPU
- **THEN** the thread keeps the guest CPU across quanta and short kernel calls until it lowers its priority, and `KeQueryBasePriorityThread` returns 16 meanwhile

#### Scenario: Higher waiter
- **WHEN** a thread at a higher priority than the holder waits for the guest CPU
- **THEN** the holder gives way at its next back edge and the waiter runs before any equal or lower waiter

#### Scenario: Equal priorities
- **WHEN** every thread runs at the same priority
- **THEN** the guest CPU goes to waiters in arrival order and the holder gives way at the quantum, as with the key off

#### Scenario: Wait on a signalled object
- **WHEN** a time-critical thread waits on an object that is already signalled while a lower thread waits for the guest CPU
- **THEN** the wait returns without the lower thread running, as on the console

#### Scenario: Key off
- **WHEN** `guest_sched` is unset
- **THEN** waiters are served in ticket order, the priority query and set use the existing path, and CreateSuspended is ignored as before

### Requirement: Suspended guest threads do not take the guest CPU
With the key on, suspend and resume of another guest thread SHALL be counted per thread and return the previous count. A suspended thread SHALL NOT receive the guest CPU, and a suspended holder SHALL give it up at its next back edge. A thread created with CreateSuspended SHALL start suspended.

#### Scenario: Spinner suspended by its owner
- **WHEN** a thread suspends a helper that loops on a back edge with no kernel call
- **THEN** the helper stops holding the guest CPU at its next back edge and is not chosen again until it is resumed
