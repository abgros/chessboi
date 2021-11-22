import subprocess
from re import findall


class Engine:
    def __init__(self, location, variantsfile, variant, skill=20):
        self.engine = subprocess.Popen(
            location,
            universal_newlines=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            bufsize=1)
        self.put(f"load {variantsfile}")
        self.put(f"setoption name UCI_Variant value {variant}")
        self.put(f"setoption name Skill Level value {skill}")

    def put(self, command):
        self.engine.stdin.write(command + "\n")

    def get(self):
        self.put("isready")
        output = []
        while True:
            text = self.engine.stdout.readline().strip()
            if text == "readyok":
                break
            if text:
                output += [text]
        return output

    def allocate(self, threads=None, memory=None):
        if threads:
            self.put(f"setoption name threads value {threads}")
        if memory: # MB
            self.put(f"setoption name hash value {memory}")
        self.get() # check that engine is ready
        return

    def analyze(self, fen, moves, movetime):
        self.put(f"position fen {fen} moves {' '.join(moves)}")
        self.put(f"go movetime {movetime}")

        # Get engine output    
        std_output = []
        while True:
            if std_output:                    
                bestmove_found = findall('bestmove .+', std_output[-1])
                if bestmove_found: 
                    bestmove = bestmove_found[0].split()[1]
                    engine_eval = findall("(?:cp|mate) [-]?\d+", ''.join(std_output))[-1]
                    break
            std_output += self.get()

        return (bestmove, engine_eval)

    def quit(self):
        self.put("quit")
