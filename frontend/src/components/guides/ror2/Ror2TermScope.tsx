import { createContext, useContext, type ReactNode } from "react";
import { ror2ReplaceTerms, type Ror2Term } from "@/lib/ror2Home";

const Ror2TermsContext = createContext<readonly Ror2Term[]>([]);

export function Ror2TermScope({ terms, children }: { terms: readonly Ror2Term[]; children: ReactNode }) {
  return <Ror2TermsContext.Provider value={terms}>{children}</Ror2TermsContext.Provider>;
}

export function useRor2TermText() {
  const terms = useContext(Ror2TermsContext);
  return (text: string) => ror2ReplaceTerms(text, terms);
}
