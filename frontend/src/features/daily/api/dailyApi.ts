import { client } from "@/shared/api/http";
import type { UserCheckinTasksPage } from "./types";

export async function fetchMyDailyTasks(params?: {
  platform?: string | null;
  page?: number;
  page_size?: number;
}) {
  const { data } = await client.get<UserCheckinTasksPage>(
    "/profile/daily-tasks",
    { params },
  );
  return data;
}
