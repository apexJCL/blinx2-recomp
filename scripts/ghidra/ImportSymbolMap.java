// Import config/symbols.toml into the open program: a primary label per
// entry (a function is renamed, or created when the analysis missed it) and
// a plate comment with the note and the source, so the listing shows where
// a name came from. Fields and code sites (kind "label") get a label only;
// the struct itself is not built (the map does not hold whole layouts yet).
// A "function" inside another function is labelled, never created.
//
// The map wins over Ghidra's own names (entity-system-spike design, Part A):
// an existing user or analysis name is replaced, and the old one is kept in
// the plate comment (Ghidra's default sub_/DAT_ names are not kept). An
// entry Ghidra refuses is printed and skipped; the rest still import.
//
// Headless (on a copy of the project, never the one under analysis/ghidra):
//   analyzeHeadless <projdir> <proj> -process xbe_flat.bin -noanalysis \
//     -scriptPath scripts/ghidra -postScript ImportSymbolMap.java config/symbols.toml
//
// The parser reads the subset of TOML symbols.toml uses: [[symbol]] tables of
// `key = value` lines with integers (decimal or 0x), booleans and basic strings. Ghidra
// ships no TOML reader, and the file's test (scripts/test_symbols.py) keeps
// it in that subset.
//
// @category XboxRecomp

import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.SourceType;
import ghidra.program.model.symbol.Symbol;

public class ImportSymbolMap extends GhidraScript {

    @Override
    protected void run() throws Exception {
        String[] args = getScriptArgs();
        File file = args.length > 0 ? new File(args[0])
                                    : askFile("symbols.toml", "Import");
        List<Map<String, Object>> entries = parse(file);

        int labels = 0, renamed = 0, created = 0, skipped = 0;
        for (Map<String, Object> e : entries) {
            Object a = e.get("addr");
            if (!(a instanceof Long)) {
                skipped++; // a field of a heap struct: no fixed address
                continue;
            }
            String name = (String) e.get("name");
            try {
                Address addr = toAddr((Long) a);
                if (currentProgram.getMemory().getBlock(addr) == null) {
                    println("not in memory: " + name + " " + addr);
                    skipped++;
                    continue;
                }
                String old = null;
                Function f = null;
                if ("function".equals(e.get("kind"))) {
                    f = getFunctionAt(addr);
                    Function in = getFunctionContaining(addr);
                    // An address inside another function is a site, not a
                    // start: creating a function there would cut its owner.
                    if (f == null && in == null) {
                        disassemble(addr);
                        f = createFunction(addr, name);
                        if (f != null) {
                            created++;
                        }
                    } else if (f == null) {
                        println("inside " + in.getName() + ", labelled: " + name + " " + addr);
                    }
                }
                if (f != null) {
                    if (!name.equals(f.getName())) {
                        if (f.getSymbol().getSource() != SourceType.DEFAULT) {
                            old = f.getName();
                        }
                        f.setName(name, SourceType.USER_DEFINED);
                        renamed++;
                    }
                } else {
                    Symbol s = getSymbolAt(addr);
                    if (s != null && s.getSource() != SourceType.DEFAULT
                            && !name.equals(s.getName())) {
                        old = s.getName();
                    }
                    createLabel(addr, name, true, SourceType.USER_DEFINED);
                    labels++;
                }
                if (old == null) {
                    old = previousWas(getPlateComment(addr));
                }
                setPlateComment(addr, plate(e, old));
            } catch (Exception ex) { // DuplicateNameException, InvalidInputException, ...
                println("skipped " + name + ": " + ex);
                skipped++;
            }
        }
        println(String.format(
            "symbols.toml: %d entries, %d functions renamed, %d created, %d labels, %d skipped",
            entries.size(), renamed, created, labels, skipped));
    }

    // The `was:` line of an earlier import, so a re-run keeps the name the
    // map first replaced instead of dropping it.
    private static String previousWas(String plate) {
        if (plate == null) {
            return null;
        }
        for (String line : plate.split("\n")) {
            if (line.startsWith("was: ")) {
                return line.substring(5);
            }
        }
        return null;
    }

    private static String plate(Map<String, Object> e, String old) {
        StringBuilder sb = new StringBuilder();
        sb.append(e.get("name"));
        if (e.containsKey("struct")) {
            sb.append(String.format(" (%s+0x%X)", e.get("struct"), e.get("offset")));
        }
        if (e.containsKey("note")) {
            sb.append("\n").append(e.get("note"));
        }
        sb.append("\nsource: ").append(e.get("source"));
        if (e.containsKey("conflict")) {
            sb.append("\nconflict: ").append(e.get("conflict"));
        }
        if (old != null) {
            sb.append("\nwas: ").append(old);
        }
        return sb.toString();
    }

    private List<Map<String, Object>> parse(File file) throws Exception {
        List<Map<String, Object>> out = new ArrayList<>();
        Map<String, Object> cur = null;
        int n = 0;
        for (String raw : Files.readAllLines(file.toPath(), StandardCharsets.UTF_8)) {
            n++;
            String line = raw.strip();
            if (line.isEmpty() || line.startsWith("#")) {
                continue;
            }
            if (line.equals("[[symbol]]")) {
                cur = new HashMap<>();
                out.add(cur);
                continue;
            }
            int eq = line.indexOf('=');
            if (cur == null || eq < 0) {
                throw new IllegalArgumentException(file + ":" + n + ": not a [[symbol]] key");
            }
            String key = line.substring(0, eq).strip();
            cur.put(key, value(line.substring(eq + 1).strip(), file, n));
        }
        return out;
    }

    private static Object value(String v, File file, int n) {
        if (v.startsWith("\"")) {
            StringBuilder sb = new StringBuilder();
            for (int i = 1; i < v.length(); i++) {
                char c = v.charAt(i);
                if (c == '\\' && i + 1 < v.length()) {
                    char d = v.charAt(++i);
                    sb.append(d == 'n' ? '\n' : d == 't' ? '\t' : d);
                } else if (c == '"') {
                    return sb.toString(); // anything after is a comment
                } else {
                    sb.append(c);
                }
            }
            throw new IllegalArgumentException(file + ":" + n + ": unterminated string");
        }
        int hash = v.indexOf('#');
        String num = (hash >= 0 ? v.substring(0, hash) : v).strip().replace("_", "");
        if (num.equals("true") || num.equals("false")) {
            return Boolean.valueOf(num);
        }
        if (num.startsWith("0x") || num.startsWith("0X")) {
            return Long.parseLong(num.substring(2), 16);
        }
        return Long.parseLong(num);
    }
}
