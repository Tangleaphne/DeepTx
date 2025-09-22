def extract_addresses(trace_item, addr_set):
                action = trace_item.get("action", {})
                if "from" in action:
                    addr_set.add(action["from"].lower())
                if "to" in action:
                    addr_set.add(action["to"].lower())
                for sub in trace_item.get("subtraces", []):
                    extract_addresses(sub, addr_set)
            
            addr_set = set()
            extract_addresses(trace_data, addr_set)
            addresses = list(addr_set)
            print(f"Found {len(addresses)} addresses")