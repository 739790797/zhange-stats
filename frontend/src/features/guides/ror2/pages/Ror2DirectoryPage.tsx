import { Ror2DirectoryView } from "@/features/guides/ror2/components/Ror2DirectoryView";
import type { Ror2PageSectionId } from "@/features/guides/ror2/model/ror2Home";

export default function Ror2DirectoryPage({ section }: { section: Ror2PageSectionId }) {
  return <Ror2DirectoryView section={section} />;
}
