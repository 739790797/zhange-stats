import { Result } from "antd";
import { PageHeader } from "@/components/PageHeader";

type Props = {
  title: string;
};

/** 预留：tasks / maps 等与 items 平级的上游域。 */
export default function TarkovReservedPage({ title }: Props) {
  return (
    <div>
      <PageHeader title={title} subtitle="逃离塔科夫" />
      <Result status="info" title="即将推出" subTitle="该数据域已预留，同步与页面尚未接入。" />
    </div>
  );
}
