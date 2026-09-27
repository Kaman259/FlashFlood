const DB_NAME = "flashflood-offline";
const DB_VERSION = 1;
const STORE_NAME = "last-known";

function openDatabase() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);

    request.onupgradeneeded = () => {
      const db = request.result;

      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME);
      }
    };

    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

export async function saveLastKnown(key, data) {
  if (!data) {
    return;
  }

  try {
    const db = await openDatabase();

    await new Promise((resolve, reject) => {
      const transaction = db.transaction(STORE_NAME, "readwrite");
      const store = transaction.objectStore(STORE_NAME);

      store.put(
        {
          data,
          savedAt: new Date().toISOString(),
        },
        key,
      );

      transaction.oncomplete = resolve;
      transaction.onerror = () => reject(transaction.error);
    });

    db.close();
  } catch (error) {
    console.warn("Could not save offline data:", error);
  }
}

export async function loadLastKnown(key) {
  try {
    const db = await openDatabase();

    const result = await new Promise((resolve, reject) => {
      const transaction = db.transaction(STORE_NAME, "readonly");
      const store = transaction.objectStore(STORE_NAME);
      const request = store.get(key);

      request.onsuccess = () => resolve(request.result ?? null);
      request.onerror = () => reject(request.error);
    });

    db.close();

    return result;
  } catch (error) {
    console.warn("Could not load offline data:", error);
    return null;
  }
}