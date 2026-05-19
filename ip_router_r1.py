# This program simulates how router R1 handles one IPv4 datagram.
# It reads an input file containing the IP header in binary and the data size.
# It then either:
#   1. prints the datagram/fragments R1 would transmit, or
#   2. prints an error message.

import sys
from pathlib import Path


EXAMPLE_DIR = Path("extra_examples")


# The subnet mask
MASK = [255, 186, 170, 85]


# IP addresses directly connected to router R1.
R1_IPS = [
    [110, 49, 32, 80],  # A1
    [110, 33, 32, 80],  # A2
    [110, 49, 32, 68],  # A3
    [110, 19, 41, 17],  # A4
]


# Routing table for router R1.
# Each row means: [destination network, route number, MTU, outgoing R1 interface IP]
R1_TABLE = [
    [[110, 48, 32, 80], 1, 1500, [110, 49, 32, 80]],
    [[110, 32, 32, 80], 2, 256, [110, 33, 32, 80]],
    [[110, 48, 32, 68], 3, 256, [110, 49, 32, 68]],
    [[110, 18, 40, 17], 4, 512, [110, 19, 41, 17]],
    [[110, 18, 40, 21], 5, 512, [110, 19, 41, 17]],
    [[110, 18, 40, 64], 5, 1500, [110, 19, 41, 17]],
    [[110, 18, 40, 20], 6, 1500, [110, 19, 41, 17]],
    [[110, 48, 32, 69], 7, 256, [110, 49, 32, 68]],
    [[110, 32, 32, 64], 7, 512, [110, 49, 32, 68]],
    [[110, 48, 32, 64], 8, 512, [110, 49, 32, 80]],
    [[110, 32, 32, 69], 9, 256, [110, 33, 32, 80]],
    [[110, 24, 40, 64], 9, 256, [110, 33, 32, 80]],
    [[110, 24, 40, 80], 9, 512, [110, 33, 32, 80]],
    [[110, 32, 32, 68], 10, 512, [110, 33, 32, 80]],
    [[110, 24, 40, 68], 10, 256, [110, 33, 32, 80]],
    [[110, 18, 40, 16], 10, 512, [110, 33, 32, 80]],
]


def ip_to_str(ip):
    # Converts an IP address list like [110, 49, 32, 80] into dotted-decimal notation: "110.49.32.80"
    return ".".join(str(x) for x in ip)


def apply_mask(ip):
    # Applies the subnet mask using bitwise AND.
    # This is how the program finds the network portion of an IP address.
    return [ip[i] & MASK[i] for i in range(4)]


def bits_to_int(bits):
    # Converts a binary string into a decimal number.
    return int(bits, 2) if bits else 0


def bits_to_ip(bits):
    # Converts 32 bits into a four-part IP address.
    return [bits_to_int(bits[i:i+8]) for i in range(0, 32, 8)]


def parse_input(filename):
    # Reads the input file.
    # The last line is the size of the data field.
    # All previous lines are assumed to be binary header bits.
    with open(filename, "r") as f:
        lines = [line.strip() for line in f if line.strip()]

    if not lines:
        raise ValueError("Error: empty input file")

    data_size = int(lines[-1])

    # Join all header lines together.
    bit_string = "".join(lines[:-1])

    # Remove anything that is not a 0 or 1.
    # This lets the file contain spaces or line breaks.
    bit_string = "".join(ch for ch in bit_string if ch in "01")

    return bit_string, data_size


def parse_header(bits):
    # Parses the IPv4 header.
    # The minimum IPv4 header is 20 bytes = 160 bits.
    if len(bits) < 160:
        raise ValueError("Error: malformed header")

    version = bits_to_int(bits[0:4])
    hlen = bits_to_int(bits[4:8])
    service = bits_to_int(bits[8:16])
    total_length = bits_to_int(bits[16:32])
    ident = bits_to_int(bits[32:48])

    flag_bits = bits[48:51]
    flag = bits_to_int(flag_bits)

    frag_offset = bits_to_int(bits[51:64])

    ttl = bits_to_int(bits[64:72])
    protocol = bits_to_int(bits[72:80])
    checksum = bits_to_int(bits[80:96])

    src = bits_to_ip(bits[96:128])
    dest = bits_to_ip(bits[128:160])

    # HLEN is measured in 32-bit words.
    # So HLEN=5 means 5 * 4 = 20 bytes.
    header_bytes = hlen * 4

    # If HLEN > 5, the extra bytes after the destination address are options.
    option_bits = bits[160:header_bytes * 8] if hlen > 5 else ""

    return {
        "version": version,
        "hlen": hlen,
        "service": service,
        "total_length": total_length,
        "ident": ident,
        "flag": flag,
        "frag_offset": frag_offset,
        "ttl": ttl,
        "protocol": protocol,
        "checksum": checksum,
        "src": src,
        "dest": dest,
        "options": parse_options(option_bits),
    }


def parse_options(option_bits):
    # Parses the IP options field.
    # The assignment only allows:
    #   code 7   = Record Route
    #   code 137 = Strict Source Route
    options = []
    i = 0

    while i + 8 <= len(option_bits):
        code = bits_to_int(option_bits[i:i+8])

        # Option code 0 means end of options.
        if code == 0:
            break

        # Option code 1 means "no operation."
        # It is one byte long and is often used for padding/alignment.
        if code == 1:
            options.append({"code": 1, "length": 1, "pointer": None, "ips": []})
            i += 8
            continue

        # Other options need at least:
        # code byte, length byte, pointer byte.
        if i + 24 > len(option_bits):
            raise ValueError("Error: malformed option")

        length = bits_to_int(option_bits[i+8:i+16])
        pointer = bits_to_int(option_bits[i+16:i+24])

        if length < 3:
            raise ValueError("Error: malformed option")

        # The option data begins after the first 3 bytes.
        option_data = option_bits[i+24:i+(length * 8)]
        ips = []

        # Every IP address inside the option is 32 bits.
        for j in range(0, len(option_data), 32):
            if j + 32 <= len(option_data):
                ips.append(bits_to_ip(option_data[j:j+32]))

        options.append({
            "code": code,
            "length": length,
            "pointer": pointer,
            "ips": ips,
        })

        i += length * 8

    return options


def validate_options(options):
    # The project says that only one option may be present.
    # It also says the only possible options are:
    #   Record Route
    #   Strict Source Route
    real_options = [o for o in options if o["code"] not in (0, 1)]

    if len(real_options) > 1:
        return "Error: more than one option"

    for opt in real_options:
        if opt["code"] not in (7, 137):
            return "Error: unsupported option"

    return None


def find_route(ip):
    # Finds the routing table row that matches the IP address.
    # It compares network values after applying the subnet mask.
    network = apply_mask(ip)

    for row in R1_TABLE:
        if apply_mask(row[0]) == network:
            return row

    return None


def source_known(src):
    # Returns True if the source address belongs to a known network.
    return find_route(src) is not None


def destination_known(dest):
    # Returns True if the destination address belongs to a known network.
    return find_route(dest) is not None


def packet_should_be_handled_by_another_router(src, dest):
    # If R1 would send the packet back out through the same network it came from,
    # another router on that source network is the correct next hop.
    src_route = find_route(src)
    dest_route = find_route(dest)

    return src_route is not None and dest_route is not None and src_route[3] == dest_route[3]


def forwarding_destination(header):
    # Strict Source Route uses the next route address as the temporary destination.
    for opt in header["options"]:
        if opt["code"] == 137:
            pointer = opt["pointer"]
            slot_index = (pointer - 4) // 4

            if pointer <= opt["length"] and 0 <= slot_index < len(opt["ips"]):
                return opt["ips"][slot_index]

    return header["dest"]


def update_options_for_forwarding(header, outgoing_ip):
    # Updates the options before forwarding.
    # Record Route: R1 writes its outgoing IP into the option list.
    # Strict Source Route: R1 replaces the next route address and updates destination.
    new_options = []

    for opt in header["options"]:

        if opt["code"] == 7:
            # Record Route option
            ips = opt["ips"][:]
            pointer = opt["pointer"]

            # Pointer starts at byte 4 of the option for the first IP slot.
            slot_index = (pointer - 4) // 4

            if pointer <= opt["length"] and 0 <= slot_index < len(ips):
                ips[slot_index] = outgoing_ip
                pointer += 4

            new_options.append({
                "code": 7,
                "length": opt["length"],
                "pointer": pointer,
                "ips": ips,
            })

        elif opt["code"] == 137:
            # Strict Source Route option
            ips = opt["ips"][:]
            pointer = opt["pointer"]

            slot_index = (pointer - 4) // 4

            if pointer <= opt["length"] and 0 <= slot_index < len(ips):
                next_dest = ips[slot_index]

                # Replace the current source route slot with R1's outgoing address.
                ips[slot_index] = outgoing_ip

                # The next address in the strict source route becomes
                # the temporary destination.
                header["dest"] = next_dest

                pointer += 4

            new_options.append({
                "code": 137,
                "length": opt["length"],
                "pointer": pointer,
                "ips": ips,
            })

    header["options"] = new_options


def option_header_words(options):
    # Calculates the new HLEN value after options are included.
    # HLEN is counted in 32-bit words, not bytes.
    if not options:
        return 5

    total = 0

    for opt in options:
        if opt["code"] == 1:
            total += 1
        else:
            total += opt["length"]

    # Padding is added until the option area is a multiple of 4 bytes.
    while total % 4 != 0:
        total += 1

    return 5 + (total // 4)


def copied_options_for_fragment(options, is_first_fragment):
    # Handles options during fragmentation.
    # According to the textbook:
    #   Record Route should only be copied into the first fragment.
    #   Strict Source Route should be copied into all fragments.
    result = []

    for opt in options:
        if opt["code"] == 7:
            if is_first_fragment:
                result.append(opt)

        elif opt["code"] == 137:
            result.append(opt)

    return result


def fragment_packet(header, data_size, mtu):
    # Splits the datagram into fragments if total length is larger than MTU.
    # If the datagram already fits, it returns one packet.
    if header["total_length"] <= mtu:
        packet = header.copy()
        packet["data_size"] = data_size
        return [packet]


    fragments = []
    remaining = data_size

    # Fragment offset is stored in units of 8 bytes.
    offset_bytes = header["frag_offset"] * 8
    frag_num = 1

    while remaining > 0:
        is_first = frag_num == 1

        # Some options are copied to every fragment, some only to the first.
        opts = copied_options_for_fragment(header["options"], is_first)

        hlen = option_header_words(opts)
        header_bytes = hlen * 4

        # Maximum data payload that can fit inside this fragment.
        max_payload = mtu - header_bytes

        if max_payload <= 0:
            raise ValueError("Error: MTU too small for header")

        # Every fragment except the last must have a payload divisible by 8.
        if remaining > max_payload:
            payload = (max_payload // 8) * 8
            more_fragments = 1
        else:
            payload = remaining
            more_fragments = 0

        frag = {
            "version": header["version"],
            "hlen": hlen,
            "service": header["service"],
            "total_length": header_bytes + payload,
            "ident": header["ident"],
            "flag": more_fragments,
            "frag_offset": offset_bytes // 8,
            "ttl": header["ttl"],
            "protocol": header["protocol"],
            "checksum": 0,
            "src": header["src"],
            "dest": header["dest"],
            "options": opts,
            "data_size": payload,
        }

        fragments.append(frag)

        remaining -= payload
        offset_bytes += payload
        frag_num += 1

    return fragments


def option_to_lines(opt):
    # Converts an option into printable output lines.
    lines = []

    if opt["code"] == 7:
        lines.append(
            f"Option=7 (Record route) Opt.length={opt['length']}, Pointer={opt['pointer']}"
        )

    elif opt["code"] == 137:
        lines.append(
            f"Option=137 (Strict source route) Opt.length={opt['length']}, Pointer={opt['pointer']}"
        )

    for ip in opt["ips"]:
        lines.append(f"Opt. IP: {ip_to_str(ip)}")

    return lines


def format_fragment(fragment, number, total):
    # Formats one fragment exactly like the assignment example.
    suffix = "st" if number == 1 else "nd" if number == 2 else "rd" if number == 3 else "th"

    protocol = "TCP" if fragment["protocol"] == 6 else fragment["protocol"]

    lines = [
        f"{number}{suffix} fragm: "
        f"VERS={fragment['version']}, HLEN={fragment['hlen']}, SERVICE={fragment['service']}, "
        f"Tot.length={fragment['total_length']}",

        f"Identif.={fragment['ident']}, Flag={fragment['flag']}, "
        f"Fragm Offset={fragment['frag_offset']}",

        f"TTL={fragment['ttl']}, Protocol={protocol}, "
        f"Checksum={fragment['checksum']}",

        f"Source Address: {ip_to_str(fragment['src'])}",

        f"Destin. Address: {ip_to_str(fragment['dest'])}",
    ]

    for opt in fragment["options"]:
        lines.extend(option_to_lines(opt))

    lines.append(f"Data Field: {fragment['data_size']} bytes")

    return "\n".join(lines)


def process(input_file, output_file):
    # Main program logic.
    # Reads input, checks errors, routes the packet, fragments if needed,
    # and writes the result to the output file.
    try:
        bits, data_size = parse_input(input_file)
        header = parse_header(bits)

        option_error = validate_options(header["options"])

        if option_error:
            message = option_error

        elif header["version"] != 4:
            message = "Error: incorrect IP version"

        elif header["protocol"] != 6:
            message = "Error: incorrect protocol"

        elif not source_known(header["src"]):
            message = "Unknown source"

        elif not destination_known(header["dest"]):
            message = "Unknown destination"

        else:
            dest_for_forwarding = forwarding_destination(header)

            if not destination_known(dest_for_forwarding):
                message = "Unknown destination"

            elif packet_should_be_handled_by_another_router(header["src"], dest_for_forwarding):
                message = "Message is discarded because it will be handled by another router"

            else:
                route = find_route(dest_for_forwarding)
                mtu = route[2]
                outgoing_ip = route[3]

                # A router decrements TTL before transmitting the datagram.
                header["ttl"] -= 1

                # Update Record Route or Strict Source Route options before forwarding.
                update_options_for_forwarding(header, outgoing_ip)

                # Fragment if total length is larger than the outgoing network MTU.
                fragments = fragment_packet(header, data_size, mtu)

                message = "\n\n".join(
                    format_fragment(fragment, i + 1, len(fragments))
                    for i, fragment in enumerate(fragments)
                )

    except Exception as e:
        # If anything unexpected happens, write the error message.
        message = str(e)

    with open(output_file, "w") as f:
        f.write(message)


def default_output_file(input_file):
    # Example: input_example.txt -> input_example_output.txt
    input_path = Path(input_file)
    suffix = input_path.suffix or ".txt"
    return str(input_path.with_name(input_path.stem + "_output" + suffix))


def resolve_input_file(input_file):
    # First try the file name exactly as typed.
    # If it is not found, try the same name inside extra_examples.
    input_path = Path(input_file)

    if input_path.exists() or input_path.parent != Path("."):
        return str(input_path)

    example_path = EXAMPLE_DIR / input_path

    if example_path.exists():
        return str(example_path)

    return str(input_path)


if __name__ == "__main__":
    # With no arguments, use the filenames commonly used for the assignment.
    # With one argument, make an output file name from the input file name.
    # With two arguments, use the provided input and output paths.
    if len(sys.argv) == 1:
        process("input.txt", "output.txt")
    elif len(sys.argv) == 2:
        input_file = resolve_input_file(sys.argv[1])
        process(input_file, default_output_file(input_file))
    elif len(sys.argv) == 3:
        process(resolve_input_file(sys.argv[1]), sys.argv[2])
    else:
        print("Usage: python ip_router_r1.py [input.txt] [output.txt]")
        sys.exit(1)
