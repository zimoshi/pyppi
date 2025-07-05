"""
Job file format executor
"""
__pyp_name__ = "jobsh"
__pyp_ver__ = "1.0.0"
__pyp_deps__ = "argparse"
__pyp_cli__ = True
__pyp_entrypoint__ = __file__
__pyp_host__ = "pyp://com.jobsh.pyp/.pyp"
__pyp_files__ = {
    "__init__.py": """
#!/usr/bin/env python3

import argparse
import subprocess
import sys
import re

def normalize_section_name(name):
    # Replace non-alphanumeric characters with hyphens
    return re.sub(r'[^a-zA-Z0-9]+', '-', name.strip()).strip('-')

def get_interpreter(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            match = re.match(r"## INTERPRETER:\s*(.+)\s*##", line)
            if match:
                return match.group(1).strip()
    return None

def parse_job_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    inside_job = False
    sections = {}
    current_section = None
    buffer = []

    for line in lines:
        if re.match(r"## JOB: .* ##", line):
            inside_job = True
            continue
        if re.match(r"## END JOB ##", line):
            if current_section:
                sections[current_section] = ''.join(buffer)
            break

        if inside_job:
            section_start = re.match(r"## SECTION: (.+) ##", line)
            section_end = re.match(r"## END SECTION ##", line)

            if section_start:
                current_section = normalize_section_name(section_start.group(1))
                buffer = []
            elif section_end:
                sections[current_section] = ''.join(buffer)
                current_section = None
            elif current_section:
                buffer.append(line)

    return sections


def get_section(parsed_sections, section_name):
    return parsed_sections.get(normalize_section_name(section_name))

def main():
    parser = argparse.ArgumentParser(description="Run a section from a .job file")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List all section names in a .job file")
    list_parser.add_argument("file", help="Path to the .job file")

    extract_parser = subparsers.add_parser("extract", help="Extract a section from a .job file")
    extract_parser.add_argument("file_and_section", help="Format: <filename>#<section-name>")

    lint_parser = subparsers.add_parser("lint", help="Check syntax of a .job file")
    lint_parser.add_argument("file", help="Path to the .job file")

    run_parser = subparsers.add_parser("run", help="Run a job section")
    run_parser.add_argument("--interpreter", help="Interpreter to use (e.g., python3.13)")
    run_parser.add_argument("file_and_section", help="Format: <filename>#<section-name>")

    args = parser.parse_args()

    if args.command == "run":
        if '#' not in args.file_and_section:
            print("Error: Must provide file and section as <file>#<section>")
            sys.exit(1)

        filepath, raw_section = args.file_and_section.split("#", 1)
        section_names = [s.strip() for s in raw_section.split(",")]
        parsed = parse_job_file(filepath)

        interpreter = args.interpreter or get_interpreter(filepath)
        if not interpreter:
            print("Error: No interpreter specified and none found in metadata.")
            sys.exit(1)

        combined_code = ""
        for section in section_names:
            code = get_section(parsed, section)
            if code is None:
                print(f"Section '{section}' not found.")
                sys.exit(1)
            combined_code += code + "\n"

        subprocess.run([interpreter, "-c", combined_code])
    elif args.command == "list":
        parsed = parse_job_file(args.file)
        if not parsed:
            print("No sections found.")
        else:
            for section in parsed:
                print(section)
    elif args.command == "extract":
        if '#' not in args.file_and_section:
            print("Error: Must provide file and section as <file>#<section>")
            sys.exit(1)

        filepath, section = args.file_and_section.split("#", 1)
        parsed = parse_job_file(filepath)
        code = get_section(parsed, section)

        if code is None:
            print(f"Section '{section}' not found.")
            sys.exit(1)

        print(code, end="")
    elif args.command == "lint":
        errors = []
        with open(args.file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        job_started = False
        job_ended = False
        section_stack = []
        section_names = set()

        for i, line in enumerate(lines, 1):
            if re.match(r"## JOB: .* ##", line):
                job_started = True
            elif re.match(r"## END JOB ##", line):
                job_ended = True
            elif match := re.match(r"## SECTION: (.+) ##", line):
                section = match.group(1).strip()
                if section in section_names:
                    errors.append(f"Line {i}: Duplicate section name '{section}'")
                section_stack.append((section, i))
                section_names.add(section)
            elif re.match(r"## END SECTION ##", line):
                if not section_stack:
                    errors.append(f"Line {i}: END SECTION without SECTION")
                else:
                    section_stack.pop()

        if not job_started:
            errors.append("Missing ## JOB: ... ## header.")
        if not job_ended:
            errors.append("Missing ## END JOB ## footer.")
        if section_stack:
            for name, line_num in section_stack:
                errors.append(f"Unclosed section '{name}' started at line {line_num}.")

        if errors:
            print("Lint failed with the following issues:")
            for err in errors:
                print(f" - {err}")
            sys.exit(1)
        else:
            print("Lint passed. ✅")

if __name__ == "__main__":
    main()
"""}
