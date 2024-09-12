import { S3Client, ListObjectsV2Command, GetObjectCommand } from '@aws-sdk/client-s3'
import { getSignedUrl } from '@aws-sdk/s3-request-presigner'

import dayjs from 'dayjs'
import customParseFormat from 'dayjs/plugin/customParseFormat.js'
import utc from 'dayjs/plugin/utc'

import { CompositeListType } from './types'

dayjs.extend(customParseFormat)
dayjs.extend(utc)


let s3Client: S3Client
let bucketName = 'himawari'

const settings = localStorage.getItem('s3-settings')
if (settings) {
    const s3Setting = JSON.parse(settings)
    s3Client = new S3Client({
        endpoint: s3Setting.endpoint,
        region: 'us-east-1',
        forcePathStyle: true,
        credentials: {
            accessKeyId: s3Setting.accessKeyId,
            secretAccessKey: s3Setting.secretAccessKey,
        },
    })
    bucketName = s3Setting.bucket
    console.log('Loading parameters from local storage')
} else {
    s3Client = new S3Client({
        endpoint: 'http://127.0.0.1:9000/',
        region: 'us-east-1',
        forcePathStyle: true,
        credentials: {
            accessKeyId: 'minioadmin',
            secretAccessKey: 'minioadmin',
        },
    })
}


function marshal(items: string[]) {
    let data: CompositeListType = {
        true_color: [],
        ir_clouds: []
    }
    const pattern = /himawari_(?<name>\w+)_(?<time>\d{8}_\d{4})/
    items.forEach((key: string) => {
        const match = key.match(pattern)
        if (match) {
            const { name, time } = match.groups as { name: 'true_color' | 'ir_clouds'; time: string }
            const datetime = dayjs(time, 'YYYYMMDD_HHmm')
            data[name].push({
                key, datetime
            })
        }
    })
    return data
}

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

export async function retrieveObject(key: string): Promise<string | undefined> {
    try {
        const command = new GetObjectCommand({ Bucket: bucketName, Key: key })
        const url = await getSignedUrl(s3Client, command, { expiresIn: 3600 })
        return url
    } catch (error) {
        console.error(error)
    }
}

export async function listObjects(startAfter: string): Promise<CompositeListType> {
    let continuationToken: string | undefined = undefined
    let items: string[] = []

    do {
        const command = new ListObjectsV2Command({
            Bucket: bucketName,
            ContinuationToken: continuationToken,
            StartAfter: startAfter
        })

        try {
            const response = await s3Client.send(command)

            if (response.Contents) {
                response.Contents.forEach((item) => {
                    items.push(item.Key as string)
                });
            }

            continuationToken = response.NextContinuationToken as string;
        } catch (error) {
            console.error(error)
            break
        }

        console.log('objects count', items.length)

    } while (continuationToken)

    return marshal(items)
}
