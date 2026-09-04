import { Typography } from "antd";
import { Link } from "react-router-dom";
import { AuthGuestShell } from "@/components/AuthGuestShell";
import { LegalLinks } from "@/components/LegalLinks";
import { legalDoc, type LegalDocId } from "@/lib/legalDocs";

export function LegalDocView({ id }: { id: LegalDocId }) {
  const doc = legalDoc(id);
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
