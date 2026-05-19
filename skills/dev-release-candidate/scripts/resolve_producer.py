import sys
from pathlib import Path

PRODUCERS = {
    "dev-analysis-architecture",
    "dev-analysis-dependencies",
    "dev-analysis-evolution",
    "dev-analysis-mission",
    "dev-analysis-quality",
    "dev-analysis-schema",
    "dev-analysis-security",
    "dev-test-contracts",
}

ROOT = Path(__file__).resolve().parents[3]


def main(argv):
    if len(argv) != 2:
        sys.stderr.write("usage: resolve_producer.py <producer-name>\n")
        return 1
    name = argv[1]
    if name not in PRODUCERS:
        sys.stderr.write("unknown producer: %s\n" % name)
        return 2
    target = ROOT / "skills" / "dev-report-framework" / "producers" / name
    sys.stdout.write(str(target) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
