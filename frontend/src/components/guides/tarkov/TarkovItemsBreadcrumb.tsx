import { Breadcrumb } from "antd";
import { Link } from "react-router-dom";

export type TarkovCrumb = {
  label: string;
  /** 有 to 则可点击跳转；最后一级通常不传 */
  to?: string;
};

type Props = {
  items: TarkovCrumb[];
};

/** 物品区路径：物品 > 弹药 > …，任一段可点回对应页 */
export function TarkovItemsBreadcrumb({ items }: Props) {
  return (
    <Breadcrumb
      style={{ marginBottom: 12 }}
      items={items.map((item, index) => ({
        key: `${index}-${item.label}`,
        title: item.to ? <Link to={item.to}>{item.label}</Link> : item.label,
      }))}
    />
  );
}
