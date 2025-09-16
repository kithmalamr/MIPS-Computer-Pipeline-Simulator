import sys
import argparse
import unittest



NUM_REGS = 32             # Number of registers in the register file
MEMORY_SIZE = 1024        # Number of words in data memory
NOP = {'opcode': 'nop'}   # Representation of a no-operation
LOG_FILE = "pipeline_log.txt"


registers = [0] * NUM_REGS      # General-purpose registers ($0–$31)
data_memory = [0] * MEMORY_SIZE # Word-addressable data memory
instruction_memory = []         # List of instruction strings
pc = 0                           # Program counter (index into instruction_memory)
cycle = 0                        # Current cycle count
instr_executed = 0               # Count of instructions that have reached WB
log_lines = []                   # Accumulates log output per cycle

# Pipeline registers between stages
pipeline = {
    'IF_ID': None,   # Between Fetch and Decode
    'ID_EX': None,   # Between Decode and Execute
    'EX_MEM': None,  # Between Execute and Memory
    'MEM_WB': None   # Between Memory and Write-Back
}


def reset(): # Restore all state to its initial, empty condition. Called before each new simulation/test
    global registers, data_memory, instruction_memory
    global pc, cycle, instr_executed, log_lines, pipeline

    registers = [0] * NUM_REGS
    data_memory = [0] * MEMORY_SIZE
    instruction_memory = []
    pc = 0
    cycle = 0
    instr_executed = 0
    log_lines = []
    pipeline = {stage: None for stage in pipeline}


def parse_instruction(line): # Turns text lines into a dictionary where opcodes, rd, rs, rt and imm if required is sought out.
    tokens = line.replace(",", "").split()
    if not tokens:
        return NOP

    opcode = tokens[0].lower()
    instr = {'opcode': opcode}

    if opcode in ('add', 'sub', 'and', 'or', 'slt'):
        # R-type format: opcode rd, rs, rt
        instr.update({
            'rd': int(tokens[1][1:]),
            'rs': int(tokens[2][1:]),
            'rt': int(tokens[3][1:])
        })
    elif opcode in ('addi', 'slti'):
        # I-type arithmetic: opcode rt, rs, imm
        instr.update({
            'rt': int(tokens[1][1:]),
            'rs': int(tokens[2][1:]),
            'imm': int(tokens[3])
        })
    elif opcode in ('lw', 'sw'):
        # Load/store: opcode rt, offset(rs)
        rt = int(tokens[1][1:])
        offset, rs = tokens[2].replace(')', '').split('(')
        instr.update({
            'rt': rt,
            'rs': int(rs[1:]),
            'imm': int(offset)
        })
    else:
        return NOP

    return instr

def resolve_labels(program):  # Remove label from a list of lines and return list of pure instructions
    label_map = {}
    pure = []
    for line in program:
        if ':' in line:
            label, rest = line.split(':', 1)
            label_map[label.strip()] = len(pure)
            if rest.strip():
                pure.append(rest.strip())
        else:
            pure.append(line.strip())
    return pure, label_map


def detect_load_use_hazard(ID_instr, EX_instr): # Look for a load-use hazard: if the EX stage is loading into rt, and the ID stage needs that same register (rs or rt), return True.
    if EX_instr and EX_instr['opcode'] == 'lw':
        rt = EX_instr.get('rt')
        return rt is not None and (ID_instr.get('rs') == rt or ID_instr.get('rt') == rt)
    return False

def detect_forwarding_sources(ID_instr):  # Determine for each source of operand whihc register to use
    forwardA, forwardB = 'REG', 'REG'
    src1, src2 = ID_instr.get('rs'), ID_instr.get('rt')

    ex_mem = pipeline['EX_MEM']
    if ex_mem and ex_mem.get('rd') not in (None, 0):
        if ex_mem['rd'] == src1:
            forwardA = 'EX'
        if ex_mem['rd'] == src2:
            forwardB = 'EX'

    mem_wb = pipeline['MEM_WB']
    if mem_wb and mem_wb.get('rd') not in (None, 0):
        if forwardA == 'REG' and mem_wb['rd'] == src1:
            forwardA = 'MEM'
        if forwardB == 'REG' and mem_wb['rd'] == src2:
            forwardB = 'MEM'

    return forwardA, forwardB

def apply_forwarding(instr, forwardA, forwardB):   # Fetching operands if required in the fowarding stage
   
    rs_val = registers[instr['rs']] if instr.get('rs') is not None else 0
    rt_val = registers[instr['rt']] if instr.get('rt') is not None else 0

    if forwardA == 'EX':
        rs_val = pipeline['EX_MEM']['result']
    elif forwardA == 'MEM':
        rs_val = pipeline['MEM_WB']['result']

    if forwardB == 'EX':
        rt_val = pipeline['EX_MEM']['result']
    elif forwardB == 'MEM':
        rt_val = pipeline['MEM_WB']['result']

    return rs_val, rt_val


def pipeline_step(): # The infamous 5-step cycle
  
    global pc, cycle, instr_executed, pipeline
    cycle += 1
    log = [f"\nCycle {cycle}"]

    
    wb = pipeline['MEM_WB'] # Write Back
    if wb and wb.get('opcode') != 'nop':
        rd = wb.get('rd')
        if rd is not None:
            registers[rd] = wb['result']
        instr_executed += 1

   
    mem = pipeline['EX_MEM']  # Memory Access 
    if mem:
        if mem['opcode'] == 'lw':
            addr = mem['addr'] // 4
            mem['result'] = data_memory[addr]
        elif mem['opcode'] == 'sw':
            data_memory[mem['addr'] // 4] = mem['val']
        pipeline['MEM_WB'] = mem
    else:
        pipeline['MEM_WB'] = None


    ex = pipeline['ID_EX']     # Execute 
    if ex:
        fA, fB = detect_forwarding_sources(ex)
        rs_val, rt_val = apply_forwarding(ex, fA, fB)

        op = ex['opcode']
        if op == 'add':
            ex['result'] = rs_val + rt_val
        elif op == 'sub':
            ex['result'] = rs_val - rt_val
        elif op == 'and':
            ex['result'] = rs_val & rt_val
        elif op == 'or':
            ex['result'] = rs_val | rt_val
        elif op == 'slt':
            ex['result'] = 1 if rs_val < rt_val else 0
        elif op == 'addi':
            ex['result'] = rs_val + ex['imm']
        elif op == 'slti':
            ex['result'] = 1 if rs_val < ex['imm'] else 0
        elif op == 'lw':
            ex['addr'] = rs_val + ex['imm']
        elif op == 'sw':
            ex['addr'] = rs_val + ex['imm']
            ex['val'] = rt_val

        
        if op in ('addi', 'slti', 'lw'): # For I-types and loads, rd field comes from rt
            ex['rd'] = ex.get('rt')
        pipeline['EX_MEM'] = ex
    else:
        pipeline['EX_MEM'] = None

  
    if pipeline['IF_ID']:   # Decode
        instr = parse_instruction(pipeline['IF_ID'])
        if detect_load_use_hazard(instr, pipeline['ID_EX']):
            log.append("Data hazard detected — Stalling")   # Bubble insertion to stall
            pipeline['ID_EX'] = pipeline['EX_MEM'] = pipeline['MEM_WB'] = None
            log_pipeline_state(log)
            return
        pipeline['ID_EX'] = instr
    else:
        pipeline['ID_EX'] = None

    
    if pc < len(instruction_memory): # Instruction Fetch
        fetched = instruction_memory[pc]
        pipeline['IF_ID'] = fetched
        log.append(f"Fetched instruction: {fetched}")
        pc += 1
    else:
        pipeline['IF_ID'] = None

    log_pipeline_state(log)

def log_pipeline_state(log): # Add contents of registers to cycle log

    log.append("Pipeline State:")
    for stage in ('IF_ID', 'ID_EX', 'EX_MEM', 'MEM_WB'):
        content = pipeline[stage] if pipeline[stage] else 'NOP'
        log.append(f"  {stage}: {content}")
    log.append(f"  Registers [0–7]: {registers[:8]}")
    log.append(f"  Instructions executed so far: {instr_executed}")
    log_lines.append("\n".join(log))

def load_program(filename):
    with open(filename) as f:
        lines = [l.strip() for l in f if l.strip()]
    code, _ = resolve_labels(lines)
    return code

def run(filename, cycles=30): # Load the program, run for the given number of cycles, then write out the log and summary
 
    global instruction_memory
    instruction_memory = load_program(filename)
    for _ in range(cycles):
        pipeline_step()

    log_lines.append(f"\nTotal instructions executed: {instr_executed}")
    with open(LOG_FILE, "w") as f:
        f.write("\n".join(log_lines))

    print(f"Simulation complete. Log written to '{LOG_FILE}'.")
    print(f"Total instructions executed: {instr_executed}")


class TestSimulator(unittest.TestCase): # Testing
    def setUp(self):
        self.program_file = 'program.txt'
        program = [
            "addi $1, $0, 5",
            "addi $2, $0, 10",
            "add  $3, $1, $2",
            "sw   $3, 0($0)",
            "lw   $4, 0($0)"
        ]
        with open(self.program_file, 'w') as f:
            f.write("\n".join(program))

    def test_program_execution(self):
        reset()
        run(self.program_file, cycles=20)
        # Verify expected register and memory results
        self.assertEqual(registers[1], 5)
        self.assertEqual(registers[2], 10)
        self.assertEqual(registers[3], 15)
        self.assertEqual(registers[4], 15)
        self.assertEqual(data_memory[0], 15)

class TestUnitFunctions(unittest.TestCase):
    def test_parse_instruction_basic(self):
        self.assertEqual(parse_instruction("and $5, $6, $7"),
                         {'opcode':'and','rd':5,'rs':6,'rt':7})
        self.assertEqual(parse_instruction("addi $2, $3, -1"),
                         {'opcode':'addi','rt':2,'rs':3,'imm':-1})
        self.assertEqual(parse_instruction(""), NOP)

    def test_detect_load_use_hazard(self):
        lw_instr = {'opcode':'lw','rt':2,'rs':0,'imm':0}
        id_instr = {'opcode':'add','rs':2,'rt':3}
        self.assertTrue(detect_load_use_hazard(id_instr, lw_instr))
        self.assertFalse(detect_load_use_hazard({'opcode':'add','rs':4,'rt':5}, lw_instr))

    def test_detect_forwarding_sources(self):
        reset()
        pipeline['EX_MEM'] = {'opcode':'add','rd':2,'result':99}
        pipeline['MEM_WB'] = {'opcode':'nop'}
        fA, fB = detect_forwarding_sources({'rs':2,'rt':3})
        self.assertEqual((fA,fB), ('EX','REG'))
        pipeline['EX_MEM'] = None
        pipeline['MEM_WB'] = {'opcode':'add','rd':3,'result':55}
        fA, fB = detect_forwarding_sources({'rs':1,'rt':3})
        self.assertEqual((fA,fB), ('REG','MEM'))

    def test_apply_forwarding(self):
        reset()
        registers[1], registers[2] = 10, 20
        pipeline['EX_MEM'] = {'opcode':'add','rd':1,'result':100}
        pipeline['MEM_WB'] = {'opcode':'add','rd':2,'result':200}
        self.assertEqual(apply_forwarding({'rs':1,'rt':2}, 'EX','EX'), (100,100))
        self.assertEqual(apply_forwarding({'rs':1,'rt':2}, 'REG','MEM'), (10,200))

    def _run_and_read_log(self, prog, cycles=20):
        reset()
        tmp = 'tmp_prog.txt'
        with open(tmp, 'w') as f:
            f.write("\n".join(prog))
        run(tmp, cycles=cycles)
        with open(LOG_FILE) as f:
            return f.read()

    def test_log_file_sanity(self):
        log = self._run_and_read_log(["addi $1,$0,1"])
        self.assertIn("Total instructions executed", log)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("program", nargs="?", help="Text file of instructions")
    parser.add_argument("--test", action="store_true", help="Run unit tests")
    args = parser.parse_args()

    if args.test:
        unittest.main(argv=[sys.argv[0]])
    elif args.program:
        run(args.program)
    else:
        print("Usage: python simulator.py <program.txt> [--test]")
