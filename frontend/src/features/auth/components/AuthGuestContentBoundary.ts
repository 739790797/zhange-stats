import { createContext, type ReactNode } from "react";

export type AuthGuestContentBoundary = (content: ReactNode) => ReactNode;

/** app/router 注入登录壳内容区的应用级错误边界，feature/auth 不反向依赖 app。 */
export const AuthGuestContentBoundaryContext = createContext<AuthGuestContentBoundary>(
  (content) => content,
);
