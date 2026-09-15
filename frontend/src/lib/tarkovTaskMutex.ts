/** 互斥任务组同一时间最多一个已完成。 */

function asId(raw: string | null | undefined): string {
  return String(raw || "").trim().toLowerCase();
}

function asIdList(ids: Iterable<string>): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const raw of ids) {
    const id = asId(raw);
    if (!id || seen.has(id)) continue;
    seen.add(id);
    out.push(id);
  }
  return out;
}

export function mutexIndexFromTasks(
  items: ReadonlyArray<{
    id?: string | null;
    mutex_ids?: readonly string[] | null;
  }>,
): Map<string, string[]> {
  const mutexById = new Map<string, string[]>();
  const add = (from: string, to: string) => {
    if (!from || !to || from === to) return;
    const row = mutexById.get(from) || [];
    if (!row.includes(to)) row.push(to);
    mutexById.set(from, row);
  };
  for (const item of items) {
    const id = asId(item.id);
    if (!id) continue;
    for (const raw of item.mutex_ids || []) {
      const other = asId(String(raw || ""));
      add(id, other);
      add(other, id);
    }
  }
  return mutexById;
}

function pickMutexWinner(
  clique: readonly string[],
  doneList: readonly string[],
  prefer: readonly string[],
): string {
  let winner = "";
  let bestPrefer = -1;
  for (const id of clique) {
    const idx = prefer.lastIndexOf(id);
    if (idx > bestPrefer) {
      winner = id;
      bestPrefer = idx;
    }
  }
  if (winner) return winner;
  let bestDone = -1;
  for (const id of clique) {
    const idx = doneList.lastIndexOf(id);
    if (idx >= bestDone) {
      winner = id;
      bestDone = idx;
    }
  }
  return winner || clique[0];
}

/** 同一互斥组里若多个已完成，只留 prefer 里最晚的，否则留完成列表里最晚的。 */
export function applyMutexLedger(
  doneIds: Iterable<string>,
  startedIds: Iterable<string>,
  failedIds: Iterable<string>,
  mutexById: ReadonlyMap<string, readonly string[]>,
  prefer?: Iterable<string>,
): { done: string[]; started: string[]; failed: string[] } {
  const doneList = asIdList(doneIds);
  const doneSet = new Set(doneList);
  const preferList = asIdList(prefer || []);
  const drop = new Set<string>();
  if (!mutexById.size) {
    return {
      done: doneList,
      started: asIdList(startedIds),
      failed: asIdList(failedIds),
    };
  }
  for (const id of doneList) {
    if (drop.has(id)) continue;
    const clique: string[] = [];
    const seen = new Set<string>();
    for (const raw of [id, ...(mutexById.get(id) || [])]) {
      const ident = asId(String(raw || ""));
      if (!ident || seen.has(ident) || !doneSet.has(ident) || drop.has(ident)) {
        continue;
      }
      seen.add(ident);
      clique.push(ident);
    }
    if (clique.length <= 1) continue;
    const winner = pickMutexWinner(clique, doneList, preferList);
    for (const other of clique) {
      if (other !== winner) drop.add(other);
    }
  }
  const done = doneList.filter((id) => !drop.has(id));
  const doneKeep = new Set(done);
  const startedSet = new Set(asIdList(startedIds));
  const extraFail = new Set(drop);
  for (const id of done) {
    for (const raw of mutexById.get(id) || []) {
      const other = asId(String(raw || ""));
      if (!other || doneKeep.has(other)) continue;
      if (startedSet.has(other)) extraFail.add(other);
    }
  }
  const failed = asIdList([...asIdList(failedIds), ...extraFail]).filter(
    (id) => !doneKeep.has(id),
  );
  const failedSet = new Set(failed);
  const started = asIdList(startedIds).filter(
    (id) => !doneKeep.has(id) && !failedSet.has(id),
  );
  return { done, started, failed };
}
