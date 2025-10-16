import dayjs from "dayjs";

// Initialize time, ensuring minutes are rounded to the nearest 10
export const roundToNearestTenMinutes = (
  date: dayjs.Dayjs | Date | string
): dayjs.Dayjs => {
  const dayjsDate = dayjs(date);
  const minutes = dayjsDate.minute();
  const roundedMinutes = Math.round(minutes / 10) * 10;
  return dayjsDate.minute(roundedMinutes).second(0).millisecond(0);
};
