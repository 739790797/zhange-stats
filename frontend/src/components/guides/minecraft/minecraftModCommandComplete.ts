export type CommandArgSpec = {
  id: string;
  kind: string;
  optional?: boolean;
  options?: { value: string }[];
};

export type CommandNodeSpec = {
  id: string;
  confirm?: string;
  args?: CommandArgSpec[];
};

export type CommandSuggestion = {
  token: string;
  line: string;
};

export type ParsedCommandLine =
  | { commandId: string; args: Record<string, string | number> }
  | { error: string };

function tokenizeLine(text: string): { tokens: string[]; trailingSpace: boolean } {
  const trailingSpace = /\s$/.test(text);
  const tokens = text.trim().split(/\s+/).filter(Boolean);
  return { tokens, trailingSpace };
}

function matchNode(tree: CommandNodeSpec[], id: string | undefined) {
  const wanted = (id || "").toLowerCase();
  if (!wanted) return null;
  return tree.find((node) => node.id.toLowerCase() === wanted) || null;
}

function longestCommonPrefix(items: string[]): string {
  if (!items.length) return "";
  let prefix = items[0];
  for (const item of items.slice(1)) {
    while (!item.toLowerCase().startsWith(prefix.toLowerCase())) {
      prefix = prefix.slice(0, -1);
      if (!prefix) return "";
    }
  }
  return prefix;
}

function argChoices(
  arg: CommandArgSpec,
  worlds: string[],
  maps: string[],
): string[] {
  if (arg.kind === "world") return worlds.filter(Boolean);
  if (arg.kind === "map") return (maps.length ? maps : worlds).filter(Boolean);
  if (arg.kind === "enum") {
    return (arg.options || []).map((row) => row.value).filter(Boolean);
  }
  return [];
}

function headForCurrentToken(
  tokens: string[],
  trailingSpace: boolean,
): string {
  if (trailingSpace || tokens.length === 0) return tokens.join(" ");
  return tokens.slice(0, -1).join(" ");
}

export function shouldAdvance(
  line: string,
  tree: CommandNodeSpec[],
): boolean {
  const { tokens } = tokenizeLine(line);
  const node = matchNode(tree, tokens[0]);
  if (!node) return false;
  const next = (node.args || [])[tokens.length - 1];
  return Boolean(next && !next.optional);
}

export function applySuggestionLine(
  line: string,
  tree: CommandNodeSpec[],
): string {
  return shouldAdvance(line, tree) ? `${line} ` : line;
}

export function suggestionsForLine(
  text: string,
  tree: CommandNodeSpec[],
  worlds: string[],
  maps: string[] = [],
): CommandSuggestion[] {
  const { tokens, trailingSpace } = tokenizeLine(text);

  if (tokens.length === 0 || (tokens.length === 1 && !trailingSpace)) {
    const prefix = (tokens[0] || "").toLowerCase();
    return tree
      .filter((node) => node.id.toLowerCase().startsWith(prefix))
      .map((node) => ({ token: node.id, line: node.id }));
  }

  const node = matchNode(tree, tokens[0]);
  if (!node) return [];

  const args = node.args || [];
  const filled = tokens.slice(1);
  const argIndex = trailingSpace ? filled.length : filled.length - 1;
  if (argIndex < 0 || argIndex >= args.length) return [];

  const current = trailingSpace ? "" : filled[filled.length - 1] || "";
  const prefix = current.toLowerCase();
  const head = headForCurrentToken(tokens, trailingSpace);

  return argChoices(args[argIndex], worlds, maps)
    .filter((choice) => choice.toLowerCase().startsWith(prefix))
    .map((choice) => ({
      token: choice,
      line: head ? `${head} ${choice}` : choice,
    }));
}

function currentArgChoices(
  text: string,
  tree: CommandNodeSpec[],
  worlds: string[],
  maps: string[],
): { choices: string[]; head: string } | null {
  const { tokens, trailingSpace } = tokenizeLine(text);
  if (tokens.length === 0 || (tokens.length === 1 && !trailingSpace)) {
    return null;
  }
  const node = matchNode(tree, tokens[0]);
  if (!node) return null;
  const args = node.args || [];
  const filled = tokens.slice(1);
  const argIndex = trailingSpace ? filled.length : filled.length - 1;
  if (argIndex < 0 || argIndex >= args.length) return null;
  const choices = argChoices(args[argIndex], worlds, maps);
  if (choices.length < 2) return null;
  return { choices, head: headForCurrentToken(tokens, trailingSpace) };
}

export function completeLine(
  text: string,
  tree: CommandNodeSpec[],
  worlds: string[],
  maps: string[] = [],
): string {
  const hits = suggestionsForLine(text, tree, worlds, maps);
  if (!hits.length) return text;

  const { tokens, trailingSpace } = tokenizeLine(text);
  const current =
    !trailingSpace && tokens.length ? tokens[tokens.length - 1] : "";

  const slot = currentArgChoices(text, tree, worlds, maps);
  if (slot && current) {
    const idx = slot.choices.findIndex(
      (choice) => choice.toLowerCase() === current.toLowerCase(),
    );
    if (idx >= 0) {
      const nextToken = slot.choices[(idx + 1) % slot.choices.length];
      const line = slot.head ? `${slot.head} ${nextToken}` : nextToken;
      return applySuggestionLine(line, tree);
    }
  }

  if (hits.length === 1) {
    return applySuggestionLine(hits[0].line, tree);
  }

  const exact = current
    ? hits.find((row) => row.token.toLowerCase() === current.toLowerCase())
    : undefined;
  if (exact && shouldAdvance(exact.line, tree)) {
    return `${exact.line} `;
  }

  const lcp = longestCommonPrefix(hits.map((row) => row.token));
  const atLcp =
    !lcp ||
    (Boolean(current) && lcp.toLowerCase() === current.toLowerCase());
  if (atLcp) {
    const idx = hits.findIndex(
      (row) => row.token.toLowerCase() === current.toLowerCase(),
    );
    const next = hits[(idx + 1) % hits.length] || hits[0];
    return applySuggestionLine(next.line, tree);
  }

  const head = headForCurrentToken(tokens, trailingSpace);
  return head ? `${head} ${lcp}` : lcp;
}

export function parseCommandLine(
  text: string,
  tree: CommandNodeSpec[],
): ParsedCommandLine {
  const tokens = text.trim().split(/\s+/).filter(Boolean);
  if (!tokens.length) return { error: "输入指令" };
  const node = matchNode(tree, tokens[0]);
  if (!node) return { error: "不支持的指令" };

  const args: Record<string, string | number> = {};
  const defs = node.args || [];
  const values = tokens.slice(1);
  if (values.length > defs.length) return { error: "参数过多" };

  for (let i = 0; i < defs.length; i += 1) {
    const def = defs[i];
    const raw = values[i];
    if (raw == null || raw === "") {
      if (def.optional) continue;
      return { error: `缺少 ${def.id}` };
    }
    if (def.kind === "int") {
      if (!/^-?\d+$/.test(raw)) return { error: `${def.id} 须为整数` };
      args[def.id] = Number(raw);
      continue;
    }
    if (def.kind === "enum") {
      const picked = (def.options || []).find(
        (row) => row.value.toLowerCase() === raw.toLowerCase(),
      );
      if (!picked) return { error: `不支持的 ${def.id}` };
      args[def.id] = picked.value;
      continue;
    }
    args[def.id] = raw;
  }

  return { commandId: node.id, args };
}
