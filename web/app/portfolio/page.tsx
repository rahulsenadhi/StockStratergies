import { PageHeader } from "@/components/desk/primitives";
import { PortfolioDesk } from "@/components/desk/portfolio/portfolio-desk";
import { loadPortfolioView } from "@/lib/desk/portfolio-view";

export const dynamic = "force-dynamic";
type SearchParams = Promise<{ [key: string]: string | string[] | undefined }>;
const first = (value: string | string[] | undefined) => (Array.isArray(value) ? value[0] : value)?.slice(0, 500);

export default async function PortfolioPage({ searchParams }: { searchParams: SearchParams }) {
  const [data, params] = await Promise.all([loadPortfolioView(), searchParams]);
  return <><PageHeader title="My portfolio" sub="What you bought, and what the model's exit rules say now." />
    <PortfolioDesk data={data} add={first(params.add)} signal={first(params.signal)} /></>;
}
