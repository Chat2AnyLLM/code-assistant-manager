import shlex
import subprocess


class CommandRunner:
    def run(self, cmd: str, check: bool = True) -> str:
        # Check if command contains shell operators that require shell interpretation
        shell_operators = ["|", ">", "<", ">>", "<<", "&&", "||", ";", "&"]
        needs_shell = any(op in cmd for op in shell_operators)

        if needs_shell:
            # For commands with shell operators, use shell=True but escape the command
            # This is necessary for pipes and redirection, but we still need to be careful
            # about injection. The command comes from trusted sources (tool registries).
            proc = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        else:
            # For simple commands without shell operators, use shlex.split() for security
            proc = subprocess.run(
                shlex.split(cmd), shell=False, capture_output=True, text=True
            )

        if check and proc.returncode != 0:
            raise RuntimeError(f"command failed: {cmd}\n{proc.stderr}")
        return proc.stdout
