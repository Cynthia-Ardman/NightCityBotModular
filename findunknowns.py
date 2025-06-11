import os
import argparse

def extract_unknown_lines(directory, output_file):
    """
    Iterates through all .conf files in the given directory,
    extracts lines that contain "= 'unknown'" (case sensitive) while
    ignoring lines that start with 'set', 'if', or 'default',
    and writes them to an output file grouped by filename.
    """

    conf_files = [f for f in os.listdir(directory) if f.endswith(".conf")]
    if not conf_files:
        print("No .conf files found in the directory.")
        return

    with open(output_file, 'w', encoding='utf-8') as out:
        for filename in sorted(conf_files):  # Sort for consistent output order
            file_path = os.path.join(directory, filename)
            unknown_lines = []

            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    stripped_line = line.strip()
                    if "= 'unknown'" in stripped_line and not stripped_line.startswith(("set", "if", "default")):
                        unknown_lines.append(stripped_line)

            # Write file header
            out.write(f"=== {filename} ===\n")
            if unknown_lines:
                out.writelines(f"{line}\n" for line in unknown_lines)
            else:
                out.write("(No unknown entries found)\n")
            out.write("\n")

    print(f"Extraction complete. Results saved to {output_file}")

def main():
    parser = argparse.ArgumentParser(description="Extract lines containing '= 'unknown'' from .conf files in a directory, excluding lines starting with 'set', 'if', or 'default'.")
    parser.add_argument("directory", help="Path to the directory containing .conf files.")
    parser.add_argument("output_file", help="Path to save the extracted unknown lines.")

    args = parser.parse_args()

    if not os.path.isdir(args.directory):
        print("Error: The specified directory does not exist.")
        return

    extract_unknown_lines(args.directory, args.output_file)

if __name__ == "__main__":
    main()
