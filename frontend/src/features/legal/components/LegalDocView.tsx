import { Typography } from "antd";
import { Link } from "react-router-dom";
import { AuthGuestShell } from "@/features/auth/components/AuthGuestShell";
import { LegalLinks } from "@/features/legal/components/LegalLinks";
import { useSitePublic } from "@/features/site/hooks/useSitePublic";
import { legalDoc, type LegalDocId } from "@/features/legal/model/legalDocs";

export function LegalDocView({ id }: { id: LegalDocId }) {
  const { data } = useSitePublic();
  const doc = legalDoc(id, data?.icp_beian_no);
  return (
    <AuthGuestShell width={560} title={doc.title} subtitle={`更新于 ${doc.updated}`}>
      {doc.paragraphs.map((text, index) => (
        <Typography.Paragraph key={index}>{text}</Typography.Paragraph>
      ))}
      <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
        <Link to="/login">返回登录</Link>
      </Typography.Paragraph>
      <LegalLinks />
    </AuthGuestShell>
  );
}
