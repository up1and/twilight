import React, { useState, useEffect } from 'react'

interface SettingModalProps {
    visible: boolean
    handleClose: () => void
}

const SettingModal: React.FC<SettingModalProps> = ({ visible, handleClose }) => {

    const [s3Settings, setS3Settings] = useState({
        endpoint: '',
        bucket: '',
        accessKeyId: '',
        secretAccessKey: '',
    })

    useEffect(() => {
        const settings = localStorage.getItem('s3-settings')
        if (settings) {
            setS3Settings(JSON.parse(settings))
        }
    }, [])

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const { name, value } = e.target;
        setS3Settings((prevData) => ({
            ...prevData,
            [name]: value,
        }))
    }

    const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault()
        localStorage.setItem('s3-settings', JSON.stringify(s3Settings))
        handleClose()
    }

    if (!visible) return null

    return (
        <div style={overlayStyle}>
            <div className='settings'>
                <h2>Preference</h2>
                <form onSubmit={handleSubmit}>
                    <div>
                        <label>
                            Endpoint:
                            <input
                                type='text'
                                name='endpoint'
                                value={s3Settings.endpoint}
                                onChange={handleChange}
                                required
                            />
                        </label>
                    </div>
                    <div>
                        <label>
                            Bucket:
                            <input
                                type='text'
                                name='bucket'
                                value={s3Settings.bucket}
                                onChange={handleChange}
                                required
                            />
                        </label>
                    </div>
                    <div>
                        <label>
                            Access Key ID:
                            <input
                                type='text'
                                name='accessKeyId'
                                value={s3Settings.accessKeyId}
                                onChange={handleChange}
                                required
                            />
                        </label>
                    </div>
                    <div>
                        <label>
                            Secret Access Key:
                            <input
                                type='password'
                                name='secretAccessKey'
                                value={s3Settings.secretAccessKey}
                                onChange={handleChange}
                                required
                            />
                        </label>
                    </div>
                    <button type='submit'>Save</button>
                </form>
            </div>
        </div>
    )
}

// Modal Style
const overlayStyle: React.CSSProperties = {
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(0, 0, 0, 0.5)', // background translucent
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    zIndex: 1000,
};

export default SettingModal
