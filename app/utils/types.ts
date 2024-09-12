import dayjs from 'dayjs'


export type CompositeType = 'ir_clouds' | 'true_color'

export interface ImageType {
    datetime: dayjs.Dayjs
    key: string
    url?: string
}

export interface CompositeListType {
    true_color: Array<ImageType>
    ir_clouds: Array<ImageType>
}
