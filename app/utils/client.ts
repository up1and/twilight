
import dayjs from 'dayjs'
import customParseFormat from 'dayjs/plugin/customParseFormat.js'
import utc from 'dayjs/plugin/utc'

dayjs.extend(customParseFormat)
dayjs.extend(utc)


export function generateCompositeName(before: number = 24): string {
    const now = dayjs.utc()
    const timeago = now.subtract(before, 'hour')
    const datePart = timeago.format('YYYY/MM/DD')
    const hour = timeago.hour()
    const minute = timeago.minute()
    const roundedMinute = Math.floor(minute / 10) * 10
    const filenamePart = timeago.format(`YYYYMMDD_${String(hour).padStart(2, '0')}${String(roundedMinute).padStart(2, '0')}`)
    const filename = `${datePart}/himawari_ir_clouds_${filenamePart}_scs.webp`

    return filename
}
