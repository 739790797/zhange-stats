import { Ror2DirectoryView } from "@/components/guides/ror2/Ror2DirectoryView";
import type { Ror2PageSectionId } from "@/lib/ror2Home";

export default function Ror2DirectoryPage({ section }: { section: Ror2PageSectionId }) {
  return <Ror2DirectoryView section={section} />;
}
