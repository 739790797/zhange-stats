import { client } from "@/shared/api/http";
import type { components } from "@/shared/api/generated/schema";

export type EmailSettings = components["schemas"]["EmailSettingsOut"];

export type EmailSettingsUpdate = components["schemas"]["EmailSettingsUpdate"];

export async function fetchEmailSettings() {
  const { data } = await client.get<EmailSettings>("/settings/email");
  return data;
}

export async function updateEmailSettings(payload: EmailSettingsUpdate) {
  const { data } = await client.put<EmailSettings>("/settings/email", payload);
  return data;
}

export async function testEmailSettings(to_email: string) {
  const { data } = await client.post<{ ok: boolean; message: string }>(
    "/settings/email/test",
    { to_email } satisfies components["schemas"]["EmailTestRequest"],
  );
  return data;
}
