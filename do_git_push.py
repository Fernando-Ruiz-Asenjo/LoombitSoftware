"""Script de un solo uso: hace git push desde el proceso Python del servidor."""
import subprocess
import sys

result = subprocess.run(
    ["git", "push"],
    cwd=r"C:\Users\fernando\loombit-new",
    capture_output=True,
    text=True,
    timeout=60,
)
print("STDOUT:", result.stdout)
print("STDERR:", result.stderr)
print("RETURNCODE:", result.returncode)
sys.exit(result.returncode)
