# Five-Stage Pipelined Processor Simulator (Python)

A teaching-oriented **five-stage pipelined MIPS-like processor simulator** written in Python.  
It models **IF → ID → EX → MEM → WB** stages with **load–use hazard detection**, **data forwarding**, a **word-addressable memory**, and **cycle-by-cycle logging** to help you visualize pipeline behavior.

---

## ✨ Features

- **Five classic stages**: Instruction Fetch, Decode, Execute, Memory, Write-Back — with explicit inter-stage latches (`IF_ID`, `ID_EX`, `EX_MEM`, `MEM_WB`).
- **Hazard handling**:
  - *Load–use hazard detection* with a one-cycle **stall/bubble** insertion. 
  - *Data forwarding* from both `EX/MEM` and `MEM/WB` to avoid unnecessary stalls. 
- **Instruction set (subset)**:
  - **R-type**: `add`, `sub`, `and`, `or`, `slt`
  - **I-type**: `addi`, `slti`, **memory**: `lw`, `sw`
  - Labels are resolved and removed before simulation.
- **Memory model**: 32 registers (`$0–$31`), `$0` hardwired to zero, and a 1K-word **word-aligned** data memory (`addr//4`).
- **Deterministic logging**: Every cycle logs pipeline latches, registers `$0–$7`, and cumulative retired instructions. 
- **Unit tests** for parsing, hazards, forwarding, ALU, and an end‑to‑end run using `unittest`. 

---

## 📦 Repo Structure

```
.
├─ simulator.py        # Main simulator and unit tests
├─ program.txt         # Sample program
├─ pipeline_log.txt    # Example cycle-by-cycle log output
└─ CEREPORT.pdf        # Design write-up and explanation
```
References: simulator, program, and log files.

---

## 🚀 Quickstart

> Requires Python 3.8+ (no external deps).

1. **Run the sample program**:

```bash
python simulator.py program.txt
```

This loads `program.txt`, runs 30 cycles by default, and writes `pipeline_log.txt` with a full trace.

2. **Run the unit tests**:

```bash
python simulator.py --test
```

Uses Python’s built-in `unittest` to verify core functionality.

---

## 🧪 Sample Program

`program.txt` demonstrates basic arithmetic, store, and load:

```asm
addi $1, $0, 5
addi $2, $0, 10
add  $3, $1, $2
sw   $3, 0($0)
lw   $4, 0($0)
```

**Expected result** after enough cycles: `$1=5`, `$2=10`, `$3=15`, `$4=15`, and `data_memory[0]=15`.

---

## 📒 Example Log Snippet

The simulator emits a detailed per-cycle log. Here’s an excerpt from `pipeline_log.txt`:

```
Cycle 5
Fetched instruction: lw $4, 0($0)
Pipeline State:
  IF_ID: lw $4, 0($0)
  ID_EX: {'opcode': 'sw', 'rt': 3, 'rs': 0, 'imm': 0}
  EX_MEM: {'opcode': 'add', 'rd': 3, 'rs': 1, 'rt': 2, 'result': 15}
  MEM_WB: {'opcode': 'addi', 'rt': 2, 'rs': 0, 'imm': 10, 'result': 10, 'rd': 2}
  Registers [0–7]: [0, 5, 0, 0, 0, 0, 0, 0]
  Instructions executed so far: 1
```

You’ll also see the hazard-induced **stall** and forwarding behavior reflected in adjacent cycles.
---

## 🧠 Design Notes

- **Decode** parses lines into structured instructions and checks **load–use hazards** against the instruction in `EX`, stalling by inserting a bubble when needed.
- **Execute** applies **forwarding** from `EX/MEM` or `MEM/WB` when sources match recent destinations, then performs ALU ops or computes addresses for `lw/sw`.
- **Memory** is word-addressed via `addr // 4` and **Write‑Back** commits before the next fetch/decode to preserve in‑order semantics.
- A complete architectural overview and reflection on future improvements (e.g., control hazards and an explicit control unit) are documented in the report.

---

## 🗺️ Roadmap

Planned/possible extensions from the design write‑up:

- Control hazards: support `beq`, `bne`, and `j` with pipeline flush/redirect.
- Dedicated control unit (cleaner control path and stage responsibilities).
- Richer statistics (bubble counts, forwarding events).
- Extended ISA: shifts, logical immediates, simple multiply (shift‑add).

---

## 📚 How It Works (High Level)

1. **Fetch**: Read `instruction_memory[pc]`, push into `IF_ID`, `pc++` (NOPs when past end).  
2. **Decode**: Parse, detect **load–use hazard**; else forward to `ID_EX`.  
3. **Execute**: Select operand sources (REG/EX/MEM), run ALU or address calc, set `rd`.  
4. **Memory**: Perform `lw/sw` on word-aligned memory (`addr//4`).  
5. **Write‑Back**: Commit results, bump retired instruction counter.

---

## 🧰 Developer Tips

- Tweak default cycles in `run(filename, cycles=30)` or pass a custom cycle count.
- `reset()` clears all global state between runs/tests.
- To add new instructions, extend `parse_instruction()` and `pipeline_step()` where ALU ops are implemented.


