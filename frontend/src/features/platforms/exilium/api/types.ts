import type { components } from "@/shared/api/generated/schema";
import type { CheckinResponse } from "@/features/platforms/shared/api/types";

export type ExiliumStatus = components["schemas"]["ExiliumStatusOut"];

export type ExiliumCheckinResponse = CheckinResponse;

export type ExiliumSmsSendResponse =
  components["schemas"]["ExiliumBindSmsSendResponse"];

export type ExiliumExchangeItem =
  components["schemas"]["ExiliumExchangeItemOut"];

export type ExiliumExchangeShop =
  components["schemas"]["ExiliumExchangeShopOut"];

export type ExiliumExchangeResult =
  components["schemas"]["ExiliumExchangeResultOut"];
