import os


def main():
    print('Bhakti Palm Art Automation starting...')
    print('Pipeline: Topic -> Hindi Bhakti Song -> Palm Art Video -> Facebook + YouTube')
    print('AI voice is disabled.')
    print('Music selection will use only configured/licensed music sources.')
    required = [
        'GEMINI_API_KEY',
        'FACEBOOK_PAGE_ID',
        'FACEBOOK_PAGE_ACCESS_TOKEN',
        'YOUTUBE_CLIENT_ID',
        'YOUTUBE_CLIENT_SECRET',
        'YOUTUBE_REFRESH_TOKEN',
    ]
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        print('Missing GitHub Secrets:', ', '.join(missing))
        print('Setup is not complete yet; no post will be published.')
        return
    print('All required secrets are present.')
    print('Full generation/posting modules will be enabled next.')


if __name__ == '__main__':
    main()
