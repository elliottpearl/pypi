#!/usr/bin/env python3
import argparse
import os
import sys
from langsci.bib.bibtools import normalize

def main():
    parser = argparse.ArgumentParser(
        description="Normalize a bibliography file (.bib or .txt) and write output to a specified file"
    )
    parser.add_argument("input_file", type=str, help="Path to the input .bib or .txt file")
    parser.add_argument("output_file", type=str, help="Path to the normalized output file")
    args = parser.parse_args()

    # Check if input file exists
    if not os.path.exists(args.input_file):
        error_msg = f"Error: File {args.input_file} not found\n"
        with open("normalizebiblog.txt", "a", encoding="utf-8") as log:
            log.write(error_msg)
        print(error_msg, file=sys.stderr)
        sys.exit(1)

    try:
        # Read the input file
        with open(args.input_file, "r", encoding="utf-8") as infile:
            rawtext = infile.read()

        # Choose normalization method based on file extension
        if args.input_file.endswith(".txt"):
            normalized = normalize(rawtext, bibtexformat=False)
        elif args.input_file.endswith(".bib"):
            normalized = normalize(rawtext, bibtexformat=True)
        else:
            raise ValueError("Unsupported file type. Use .bib or .txt")

        # Write the output
        with open(args.output_file, "w", encoding="utf-8") as outfile:
            outfile.write(normalized)

        print(f"Successfully wrote normalized output to {args.output_file}")

    except ImportError as e:
        error_msg = f"Import error: {e}\n"
        with open("normalizebiblog.txt", "a", encoding="utf-8") as log:
            log.write(error_msg)
        print(error_msg, file=sys.stderr)
        sys.exit(1)

    except Exception as e:
        error_msg = f"Error processing file: {e}\n"
        with open("normalizebiblog.txt", "a", encoding="utf-8") as log:
            log.write(error_msg)
        print(error_msg, file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
