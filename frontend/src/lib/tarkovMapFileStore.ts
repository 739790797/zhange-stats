import {
  mapFileKeysToEvict,
  TARKOV_MAP_FILE_CACHE_MAX,
  type TarkovMapFileRecord,
} from "./tarkovMapFileCache";

const DB_NAME = "zhange-tarkov-map-files";
const STORE = "files";
const ETAG_STORE = "etags";
const DB_VERSION = 2;

type TarkovMapFileEtagRecord = {
  etag: string;
  savedAt: number;
};

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === "undefined") {
      reject(new Error("indexedDB unavailable"));
      return;
    }
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = (event) => {
      const db = req.result;
      const tx = req.transaction;
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE);
      }
      if (!db.objectStoreNames.contains(ETAG_STORE)) {
        db.createObjectStore(ETAG_STORE);
      }
      if (event.oldVersion < 2 && tx) {
        const files = tx.objectStore(STORE);
        const etags = tx.objectStore(ETAG_STORE);
        const cursorReq = files.openCursor();
        cursorReq.onsuccess = () => {
          const cursor = cursorReq.result;
          if (!cursor) return;
          const rec = cursor.value as TarkovMapFileRecord | undefined;
          if (typeof cursor.key === "string" && rec?.etag) {
            etags.put(
              { etag: rec.etag, savedAt: rec.savedAt || 0 },
              cursor.key,
            );
          }
          cursor.continue();
        };
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error ?? new Error("idb open failed"));
  });
}

function idbReq<T>(req: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error ?? new Error("idb request failed"));
  });
}

function waitTx(tx: IDBTransaction): Promise<void> {
  return new Promise((resolve, reject) => {
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error ?? new Error("idb tx failed"));
    tx.onabort = () => reject(tx.error ?? new Error("idb tx aborted"));
  });
}

export async function loadAllMapFileEtags(): Promise<Map<string, string>> {
  const out = new Map<string, string>();
  const db = await openDb();
  try {
    if (!db.objectStoreNames.contains(ETAG_STORE)) return out;
    const tx = db.transaction(ETAG_STORE, "readonly");
    const store = tx.objectStore(ETAG_STORE);
    const [keys, vals] = await Promise.all([
      idbReq(store.getAllKeys()),
      idbReq(store.getAll()),
    ]);
    await waitTx(tx);
    const recs = vals as TarkovMapFileEtagRecord[];
    (keys as IDBValidKey[]).forEach((key, index) => {
      if (typeof key !== "string") return;
      const rec = recs[index];
      if (rec?.etag) out.set(key, rec.etag);
    });
  } finally {
    db.close();
  }
  return out;
}

export async function loadMapFile(
  key: string,
): Promise<TarkovMapFileRecord | undefined> {
  const db = await openDb();
  try {
    const tx = db.transaction(STORE, "readonly");
    const rec = (await idbReq(
      tx.objectStore(STORE).get(key),
    )) as TarkovMapFileRecord | undefined;
    await waitTx(tx);
    if (rec && rec.etag) return rec;
    return undefined;
  } finally {
    db.close();
  }
}

export async function saveMapFile(
  key: string,
  record: TarkovMapFileRecord,
): Promise<void> {
  const db = await openDb();
  try {
    const stores = [STORE, ETAG_STORE].filter((name) =>
      db.objectStoreNames.contains(name),
    );
    const putTx = db.transaction(stores, "readwrite");
    putTx.objectStore(STORE).put(record, key);
    if (stores.includes(ETAG_STORE)) {
      putTx.objectStore(ETAG_STORE).put(
        { etag: record.etag, savedAt: record.savedAt },
        key,
      );
    }
    await waitTx(putTx);

    const readTx = db.transaction(STORE, "readonly");
    const readStore = readTx.objectStore(STORE);
    const [keys, vals] = await Promise.all([
      idbReq(readStore.getAllKeys()),
      idbReq(readStore.getAll()),
    ]);
    await waitTx(readTx);

    const entries: { key: string; savedAt: number }[] = [];
    (keys as IDBValidKey[]).forEach((itemKey, index) => {
      if (typeof itemKey !== "string") return;
      const rec = (vals as TarkovMapFileRecord[])[index];
      entries.push({ key: itemKey, savedAt: rec?.savedAt || 0 });
    });
    const evict = mapFileKeysToEvict(entries, TARKOV_MAP_FILE_CACHE_MAX);
    if (!evict.length) return;

    const delTx = db.transaction(stores, "readwrite");
    for (const itemKey of evict) {
      delTx.objectStore(STORE).delete(itemKey);
      if (stores.includes(ETAG_STORE)) {
        delTx.objectStore(ETAG_STORE).delete(itemKey);
      }
    }
    await waitTx(delTx);
  } finally {
    db.close();
  }
}
