# CS5710 Computer Networks Project

This project simulates how router R1 handles one IPv4 datagram. The program reads an input file containing an IPv4 header written in binary, plus the decimal size of the data field, and writes the datagram or fragments that R1 would transmit.

## Assignment Summary

The program implements the IP forwarding behavior for router R1 using the routing table and subnet mask from the class assignment. For each input datagram, the program checks the header fields, verifies the source and destination networks, processes supported IP options, and fragments the datagram when the outgoing network MTU requires it.

Supported IP options:

- Record Route, option code `7`
- Strict Source Route, option code `137`

If an error is found, the program writes the appropriate error message instead of forwarding the datagram.

## Files

- `ip_router_r1.py` - main Python program
- `input.txt` - default input file
- `output.txt` - default output file created by the program

Each input file should contain only one datagram.

## Input Format

The input file contains:

1. The IPv4 header written as `0`s and `1`s
2. The data field size as a decimal number on the final line

Example:

```text
01000111000000000000000111000100
00000000000110010000000000000000
00000111000001100000000000000000
01101110001100010010000101001100
01101110001000000010000101011000
00000111000001110000010000000000
00000000000000000000000000000000
424
```

## How to Run

Run with the default files:

```bash
python ip_router_r1.py
```

This reads `input.txt` and writes `output.txt`.

Run with a different input file:

```bash
python ip_router_r1.py input_example.txt
```

This creates an output file named `input_example_output.txt`.

Run with a specific input and output file:

```bash
python ip_router_r1.py input_example.txt output_example.txt
```

## Extra Test Inputs

For additional examples, make separate input files instead of adding multiple datagrams to `input.txt`. The assignment states that each input file contains only one datagram.

Good examples:

```text
input_record_route.txt
input_strict_source_route.txt
input_unknown_source.txt
input_discard.txt
input_no_fragment.txt
```

Then run one at a time:

```bash
python ip_router_r1.py input_record_route.txt
```

## Notes

- The checksum output is always `0`, as allowed by the assignment.
- The program assumes TCP protocol value `6`.
- If the datagram is larger than the outgoing MTU, the program outputs each fragment separately.
