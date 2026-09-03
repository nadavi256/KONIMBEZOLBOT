import type { Metadata } from "next";
import { CityDayPage, cityDayMetadata } from "@/components/pages/CityDayPage";

export const revalidate = 3600;
export const dynamicParams = true;

type Props = { params: Promise<{ city: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { city } = await params;
  return cityDayMetadata(city, "tomorrow");
}

export default async function TomorrowPage({ params }: Props) {
  const { city } = await params;
  return <CityDayPage citySlug={city} mode="tomorrow" />;
}
