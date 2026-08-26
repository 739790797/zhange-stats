import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { PersistQueryClientProvider } from "@tanstack/react-query-persist-client";
import { createSyncStoragePersister } from "@tanstack/query-sync-storage-persister";
import dayjs from "dayjs";
import "dayjs/locale/zh-cn";
import advancedFormat from "dayjs/plugin/advancedFormat";
import customParseFormat from "dayjs/plugin/customParseFormat";
import isoWeek from "dayjs/plugin/isoWeek";
import localeData from "dayjs/plugin/localeData";
import timezone from "dayjs/plugin/timezone";
import utc from "dayjs/plugin/utc";
import weekday from "dayjs/plugin/weekday";
import weekOfYear from "dayjs/plugin/weekOfYear";
import weekYear from "dayjs/plugin/weekYear";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./index.css";
import "@/lib/time";
import {
  QUERY_PERSIST_KEY,
  QUERY_PERSIST_MAX_AGE_MS,
  shouldDehydratePersistedQuery,
} from "@/lib/queryCache";

dayjs.extend(utc);
dayjs.extend(timezone);
dayjs.extend(customParseFormat);
dayjs.extend(advancedFormat);
dayjs.extend(weekday);
dayjs.extend(localeData);
dayjs.extend(weekOfYear);
dayjs.extend(weekYear);
dayjs.extend(isoWeek);
dayjs.locale("zh-cn");

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

function sessionStorageOrNull(): Storage | null {
  try {
    const storage = window.sessionStorage;
    storage.getItem(QUERY_PERSIST_KEY);
    return storage;
  } catch {
    return null;
  }
}

const persistStorage = sessionStorageOrNull();
const queryPersister = persistStorage
  ? createSyncStoragePersister({
      storage: persistStorage,
      key: QUERY_PERSIST_KEY,
    })
  : null;

const appTree = queryPersister ? (
  <PersistQueryClientProvider
    client={queryClient}
    persistOptions={{
      persister: queryPersister,
      maxAge: QUERY_PERSIST_MAX_AGE_MS,
      dehydrateOptions: {
        shouldDehydrateQuery: (query) => shouldDehydratePersistedQuery(query),
      },
    }}
  >
    <App />
  </PersistQueryClientProvider>
) : (
  <QueryClientProvider client={queryClient}>
    <App />
  </QueryClientProvider>
);

createRoot(document.getElementById("root")!).render(
  <StrictMode>{appTree}</StrictMode>,
);
