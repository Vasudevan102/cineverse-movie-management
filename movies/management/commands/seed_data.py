import os
import datetime
import urllib.request
import urllib.parse
import json
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model
from movies.models import Movie, Genre, Language, CastMember, MovieImage
from booking.models import Theater, Show, Booking, Payment
from reviews.models import Review

User = get_user_model()

class Command(BaseCommand):
    help = "Seeds 2026 Tamil & International movies, TMDB images, theaters, shows, and demo bookings for CineVerse"

    def fetch_tmdb_images(self, movie_title):
        """Attempts to fetch poster & backdrop URLs from TMDB API if TMDB_API_KEY is available."""
        api_key = os.environ.get("TMDB_API_KEY")
        if not api_key:
            return None
        try:
            query = urllib.parse.quote(movie_title)
            url = f"https://api.themoviedb.org/3/search/movie?api_key={api_key}&query={query}"
            req = urllib.request.Request(url, headers={'User-Agent': 'CineVerseApp/1.0'})
            with urllib.request.urlopen(req, timeout=4) as resp:
                data = json.loads(resp.read().decode())
                if data.get('results'):
                    first = data['results'][0]
                    p_path = first.get('poster_path')
                    b_path = first.get('backdrop_path')
                    res = {}
                    if p_path:
                        res['poster'] = f"https://image.tmdb.org/t/p/w500{p_path}"
                    if b_path:
                        res['backdrop'] = f"https://image.tmdb.org/t/p/original{b_path}"
                    return res if res else None
        except Exception:
            pass
        return None

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Starting CineVerse comprehensive seed data generation..."))

        # 1. Seed Languages
        languages_data = [
            ("Tamil", "ta"),
            ("English", "en"),
            ("Hindi", "hi"),
            ("Telugu", "te"),
            ("Malayalam", "ml"),
            ("Kannada", "kn"),
        ]
        language_objs = {}
        for name, code in languages_data:
            lang, _ = Language.objects.get_or_create(code=code, defaults={'name': name})
            language_objs[code] = lang

        # 2. Seed Genres
        genres_data = [
            "Action", "Comedy", "Drama", "Thriller", "Horror", "Romance",
            "Sci-Fi", "Adventure", "Animation", "Crime", "Fantasy", "Family",
            "Mystery", "Sports", "Political"
        ]
        genre_objs = {}
        for g_name in genres_data:
            g_obj, _ = Genre.objects.get_or_create(name=g_name)
            genre_objs[g_name] = g_obj

        # 3. Seed Cast Members with photos
        cast_data = [
            ("Vijay", "Thalapathy", "Renowned Indian actor known for high-octane action blockbusters.", "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=200&auto=format&fit=crop&q=80"),
            ("Rajinikanth", "Superstar", "Iconic actor with a massive legendary fan base worldwide.", "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=200&auto=format&fit=crop&q=80"),
            ("Kamal Haasan", "Ulaganayagan", "Master of Indian cinema acclaimed for versatility and craft.", "https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=200&auto=format&fit=crop&q=80"),
            ("Suriya", "Rolex / Hero", "Award-winning actor known for intense portrayals and cinema.", "https://images.unsplash.com/photo-1519085360753-af0119f7cbe7?w=200&auto=format&fit=crop&q=80"),
            ("Ajith Kumar", "AK", "Massive stardom actor famous for action thrillers and racing.", "https://images.unsplash.com/photo-1506794778202-cad84cf45f1d?w=200&auto=format&fit=crop&q=80"),
            ("Dhanush", "Karthik", "International actor celebrated for realistic acting.", "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=200&auto=format&fit=crop&q=80"),
            ("Sivakarthikeyan", "SK", "Popular entertainer loved by family audiences across Tamil Nadu.", "https://images.unsplash.com/photo-1539571696357-5a69c17a67c6?w=200&auto=format&fit=crop&q=80"),
            ("Trisha Krishnan", "Kunduvan", "Leading Indian actress with decades of top-tier success.", "https://images.unsplash.com/photo-1544005313-94ddf0286df2?w=200&auto=format&fit=crop&q=80"),
            ("Nayanthara", "Lady Superstar", "Prominent leading actress across South Indian film industries.", "https://images.unsplash.com/photo-1517841905240-472988babdf9?w=200&auto=format&fit=crop&q=80"),
            ("Robert Downey Jr.", "Doctor Doom / Tony Stark", "Acclaimed Hollywood actor iconic for global blockbuster roles.", "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=200&auto=format&fit=crop&q=80"),
            ("Cillian Murphy", "J. Robert Oppenheimer", "Oscar-winning Irish actor famed for cerebral character roles.", "https://images.unsplash.com/photo-1492562080023-ab3db95bfbce?w=200&auto=format&fit=crop&q=80"),
            ("Tom Holland", "Peter Parker / Spider-Man", "Global superstar actor leading Marvel Spider-Man franchise.", "https://images.unsplash.com/photo-1539571696357-5a69c17a67c6?w=200&auto=format&fit=crop&q=80"),
            ("Zendaya", "MJ", "Acclaimed actress celebrated across Dune and Spider-Man.", "https://images.unsplash.com/photo-1524504388940-b1c1722653e1?w=200&auto=format&fit=crop&q=80"),
            ("Shah Rukh Khan", "Pathaan", "King of Bollywood with global appeal.", "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=200&auto=format&fit=crop&q=80"),
            ("Prabhas", "Karna / Amarendra", "Pan-Indian superstar actor.", "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=200&auto=format&fit=crop&q=80"),
            ("Allu Arjun", "Pushpa Raj", "Icon Star known for blockbuster mass action films.", "https://images.unsplash.com/photo-1519085360753-af0119f7cbe7?w=200&auto=format&fit=crop&q=80"),
            ("Fahadh Faasil", "Bhanwar / Ranga", "Powerhouse actor famed for nuanced portrayals.", "https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=200&auto=format&fit=crop&q=80"),
            ("Rishab Shetty", "Shiva", "Director and actor of cultural blockbuster phenomenon.", "https://images.unsplash.com/photo-1506794778202-cad84cf45f1d?w=200&auto=format&fit=crop&q=80"),
        ]
        cast_objs = []
        for name, char_name, bio, p_url in cast_data:
            member, _ = CastMember.objects.get_or_create(
                name=name,
                defaults={'character_name': char_name, 'biography': bio, 'photo_url': p_url}
            )
            if not member.photo_url:
                member.photo_url = p_url
                member.save()
            cast_objs.append(member)

        # 4. Master Movies Dataset (Including June-August 2026 Tamil & Worldwide releases)
        movies_dataset = [
            # --- 2026 June Tamil Releases ---
            {
                "title": "Con City",
                "description": "A high-stakes comedy crime thriller following a quirky squad of small-time hustlers who inadvertently stumble upon a major urban syndicate in Chennai.",
                "duration": 145,
                "age_certificate": "U/A",
                "language": language_objs["ta"],
                "genres": [genre_objs["Comedy"], genre_objs["Crime"], genre_objs["Family"]],
                "director": "Badri",
                "trailer_url": "https://www.youtube.com/watch?v=Po3jStA673E",
                "release_date": datetime.date(2026, 6, 26),
                "rating": 4.5,
                "poster": "https://images.unsplash.com/photo-1536440136628-849c177e76a1?w=600&auto=format&fit=crop&q=80",
                "backdrop": "https://images.unsplash.com/photo-1517604931442-7e0c8ed2963c?w=1200&auto=format&fit=crop&q=80",
            },
            {
                "title": "Heartin",
                "description": "A heartwarming romantic comedy exploring young love, friendship, and unexpected second chances in modern urban Tamil Nadu.",
                "duration": 138,
                "age_certificate": "U",
                "language": language_objs["ta"],
                "genres": [genre_objs["Comedy"], genre_objs["Romance"]],
                "director": "Vishnu",
                "trailer_url": "https://www.youtube.com/watch?v=r_r2Z6tU19g",
                "release_date": datetime.date(2026, 6, 26),
                "rating": 4.4,
                "poster": "https://images.unsplash.com/photo-1518676599602-2170e6296ee3?w=600&auto=format&fit=crop&q=80",
                "backdrop": "https://images.unsplash.com/photo-1492684223066-81342ee5ff30?w=1200&auto=format&fit=crop&q=80",
            },
            {
                "title": "Andharan: The Hunter",
                "description": "An intense mystery thriller centering on a relentless investigator probing a series of mysterious forest night occurrences.",
                "duration": 152,
                "age_certificate": "U/A",
                "language": language_objs["ta"],
                "genres": [genre_objs["Mystery"], genre_objs["Thriller"], genre_objs["Romance"]],
                "director": "Rajeevan",
                "trailer_url": "https://www.youtube.com/watch?v=OKBMCL-frPU",
                "release_date": datetime.date(2026, 6, 26),
                "rating": 4.6,
                "poster": "https://images.unsplash.com/photo-1509198397868-475647b2a1e5?w=600&auto=format&fit=crop&q=80",
                "backdrop": "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?w=1200&auto=format&fit=crop&q=80",
            },
            {
                "title": "Angikaaram",
                "description": "An inspiring sports action drama depicting an underdog athlete fighting social barriers to reach national championship glory.",
                "duration": 160,
                "age_certificate": "U",
                "language": language_objs["ta"],
                "genres": [genre_objs["Action"], genre_objs["Sports"]],
                "director": "Saravanan",
                "trailer_url": "https://www.youtube.com/watch?v=hylIXfZeB4c",
                "release_date": datetime.date(2026, 6, 26),
                "rating": 4.7,
                "poster": "https://images.unsplash.com/photo-1461896836934-ffe607ba8211?w=600&auto=format&fit=crop&q=80",
                "backdrop": "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?w=1200&auto=format&fit=crop&q=80",
            },
            {
                "title": "Ananthan Kaadu",
                "description": "A high-stakes political action thriller surrounding land rights, forest conservation, and a fearless community leader.",
                "duration": 158,
                "age_certificate": "U/A",
                "language": language_objs["ta"],
                "genres": [genre_objs["Action"], genre_objs["Political"], genre_objs["Thriller"]],
                "director": "Sundar",
                "trailer_url": "https://www.youtube.com/watch?v=34dM3y2sW_Q",
                "release_date": datetime.date(2026, 6, 25),
                "rating": 4.6,
                "poster": "https://images.unsplash.com/photo-1448375240586-882707db888b?w=600&auto=format&fit=crop&q=80",
                "backdrop": "https://images.unsplash.com/photo-1470071459604-3b5ec3a7fe05?w=1200&auto=format&fit=crop&q=80",
            },
            {
                "title": "Moondram Kan",
                "description": "A gripping crime investigation thriller exploring technological surveillance and a detective racing against time.",
                "duration": 142,
                "age_certificate": "U/A",
                "language": language_objs["ta"],
                "genres": [genre_objs["Crime"], genre_objs["Mystery"], genre_objs["Thriller"]],
                "director": "Velu",
                "trailer_url": "https://www.youtube.com/watch?v=OKBMCL-frPU",
                "release_date": datetime.date(2026, 6, 12),
                "rating": 4.5,
                "poster": "https://images.unsplash.com/photo-1478760329108-5c3ed9d495a0?w=600&auto=format&fit=crop&q=80",
                "backdrop": "https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?w=1200&auto=format&fit=crop&q=80",
            },
            {
                "title": "Valluvan",
                "description": "An action-packed vigilante saga of an ethical hero dismantling corrupt networks across the city.",
                "duration": 155,
                "age_certificate": "U/A",
                "language": language_objs["ta"],
                "genres": [genre_objs["Action"], genre_objs["Thriller"]],
                "director": "Murugadoss",
                "trailer_url": "https://www.youtube.com/watch?v=Po3jStA673E",
                "release_date": datetime.date(2026, 6, 12),
                "rating": 4.6,
                "poster": "https://images.unsplash.com/photo-1579783902614-a3fb3927b675?w=600&auto=format&fit=crop&q=80",
                "backdrop": "https://images.unsplash.com/photo-1534447677768-be436bb09401?w=1200&auto=format&fit=crop&q=80",
            },
            {
                "title": "Sannidhanam P O",
                "description": "An emotional action drama following a devotion-filled journey and a hero standing up for sacred traditions.",
                "duration": 148,
                "age_certificate": "U",
                "language": language_objs["ta"],
                "genres": [genre_objs["Action"], genre_objs["Drama"], genre_objs["Romance"]],
                "director": "Rajeev",
                "trailer_url": "https://www.youtube.com/watch?v=8mrVn23Z5L4",
                "release_date": datetime.date(2026, 6, 5),
                "rating": 4.7,
                "poster": "https://images.unsplash.com/photo-1519817650390-64a93db51149?w=600&auto=format&fit=crop&q=80",
                "backdrop": "https://images.unsplash.com/photo-1506744038136-46273834b3fb?w=1200&auto=format&fit=crop&q=80",
            },
            {
                "title": "Parimala and Co",
                "description": "A laugh-out-loud comedy thriller about a quirky family business caught in absurd detective scenarios.",
                "duration": 136,
                "age_certificate": "U",
                "language": language_objs["ta"],
                "genres": [genre_objs["Comedy"], genre_objs["Thriller"]],
                "director": "Karthik",
                "trailer_url": "https://www.youtube.com/watch?v=L0yEMF8P84E",
                "release_date": datetime.date(2026, 6, 5),
                "rating": 4.4,
                "poster": "https://images.unsplash.com/photo-1514306191717-452ec28c7814?w=600&auto=format&fit=crop&q=80",
                "backdrop": "https://images.unsplash.com/photo-1517841905240-472988babdf9?w=1200&auto=format&fit=crop&q=80",
            },

            # --- 2026 July Tamil Releases ---
            {
                "title": "Idhayam Murali",
                "description": "A touching family drama and romantic chronicle spanning two decades of unconditional bond and nostalgic melody.",
                "duration": 162,
                "age_certificate": "U",
                "language": language_objs["ta"],
                "genres": [genre_objs["Drama"], genre_objs["Family"], genre_objs["Romance"]],
                "director": "Selvam",
                "trailer_url": "https://www.youtube.com/watch?v=r_r2Z6tU19g",
                "release_date": datetime.date(2026, 7, 10),
                "rating": 4.8,
                "poster": "https://images.unsplash.com/photo-1474552226712-ac0f0961a954?w=600&auto=format&fit=crop&q=80",
                "backdrop": "https://images.unsplash.com/photo-1518173946687-a4c8a383392e?w=1200&auto=format&fit=crop&q=80",
            },
            {
                "title": "Gatta Kusthi 2",
                "description": "The hilarious sequel continuing the wrestling rivalry and humorous marital clashes in rural Tamil Nadu.",
                "duration": 146,
                "age_certificate": "U",
                "language": language_objs["ta"],
                "genres": [genre_objs["Comedy"], genre_objs["Drama"], genre_objs["Family"]],
                "director": "Chella Ayyavu",
                "trailer_url": "https://www.youtube.com/watch?v=Y5BeWdODb7U",
                "release_date": datetime.date(2026, 7, 3),
                "rating": 4.7,
                "poster": "https://images.unsplash.com/photo-1517649763962-0c623266010b?w=600&auto=format&fit=crop&q=80",
                "backdrop": "https://images.unsplash.com/photo-1461896836934-ffe607ba8211?w=1200&auto=format&fit=crop&q=80",
            },
            {
                "title": "Anbe Diana",
                "description": "A vibrant romantic comedy centered around college life, music festivals, and humorous romantic misadventures.",
                "duration": 140,
                "age_certificate": "U",
                "language": language_objs["ta"],
                "genres": [genre_objs["Comedy"], genre_objs["Romance"]],
                "director": "Vimal",
                "trailer_url": "https://www.youtube.com/watch?v=r_r2Z6tU19g",
                "release_date": datetime.date(2026, 7, 17),
                "rating": 4.5,
                "poster": "https://images.unsplash.com/photo-1529156069898-49953e39b3ac?w=600&auto=format&fit=crop&q=80",
                "backdrop": "https://images.unsplash.com/photo-1492684223066-81342ee5ff30?w=1200&auto=format&fit=crop&q=80",
            },
            {
                "title": "Arjunan Per Paththu",
                "description": "A powerful character-driven emotional drama exploring family ethics and village tradition.",
                "duration": 150,
                "age_certificate": "U/A",
                "language": language_objs["ta"],
                "genres": [genre_objs["Drama"]],
                "director": "Arunkumar",
                "trailer_url": "https://www.youtube.com/watch?v=34dM3y2sW_Q",
                "release_date": datetime.date(2026, 7, 17),
                "rating": 4.6,
                "poster": "https://images.unsplash.com/photo-1485846234645-a62644f84728?w=600&auto=format&fit=crop&q=80",
                "backdrop": "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?w=1200&auto=format&fit=crop&q=80",
            },
            {
                "title": "Toxsick",
                "description": "A moody dark drama detailing subterranean city secrets and an unexpected protagonist.",
                "duration": 154,
                "age_certificate": "A",
                "language": language_objs["ta"],
                "genres": [genre_objs["Drama"]],
                "director": "Geetu",
                "trailer_url": "https://www.youtube.com/watch?v=OKBMCL-frPU",
                "release_date": datetime.date(2026, 7, 3),
                "rating": 4.4,
                "poster": "https://images.unsplash.com/photo-1509198397868-475647b2a1e5?w=600&auto=format&fit=crop&q=80",
                "backdrop": "https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?w=1200&auto=format&fit=crop&q=80",
            },
            {
                "title": "Uyar",
                "description": "An uplifting drama highlighting educational aspiration and perseverance in rural Tamil Nadu.",
                "duration": 142,
                "age_certificate": "U",
                "language": language_objs["ta"],
                "genres": [genre_objs["Drama"]],
                "director": "Ramesh",
                "trailer_url": "https://www.youtube.com/watch?v=hylIXfZeB4c",
                "release_date": datetime.date(2026, 7, 1),
                "rating": 4.6,
                "poster": "https://images.unsplash.com/photo-1503676260728-1c00da094a0b?w=600&auto=format&fit=crop&q=80",
                "backdrop": "https://images.unsplash.com/photo-1509062522246-3755977927d7?w=1200&auto=format&fit=crop&q=80",
            },

            # --- 2026 August Tamil Releases ---
            {
                "title": "Vishwanath and Sons",
                "description": "A flagship August 2026 family drama chronicling a multi-generational textile dynasty navigating modern enterprise challenges.",
                "duration": 165,
                "age_certificate": "U",
                "language": language_objs["ta"],
                "genres": [genre_objs["Drama"], genre_objs["Family"]],
                "director": "Kumar",
                "trailer_url": "https://www.youtube.com/watch?v=KsH1O2uIeUk",
                "release_date": datetime.date(2026, 8, 14),
                "rating": 4.8,
                "poster": "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=600&auto=format&fit=crop&q=80",
                "backdrop": "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=1200&auto=format&fit=crop&q=80",
            },
            {
                "title": "Hi",
                "description": "A delightful August 2026 romantic comedy-drama exploring modern relationship dynamics and humorous tech startup life.",
                "duration": 145,
                "age_certificate": "U/A",
                "language": language_objs["ta"],
                "genres": [genre_objs["Drama"], genre_objs["Comedy"], genre_objs["Romance"]],
                "director": "Anand",
                "trailer_url": "https://www.youtube.com/watch?v=r_r2Z6tU19g",
                "release_date": datetime.date(2026, 8, 14),
                "rating": 4.7,
                "poster": "https://images.unsplash.com/photo-1522071820081-009f0129c71c?w=600&auto=format&fit=crop&q=80",
                "backdrop": "https://images.unsplash.com/photo-1517245386807-bb43f82c33c4?w=1200&auto=format&fit=crop&q=80",
            },
            {
                "title": "Irumudi Kattu",
                "description": "An August 2026 spiritual socio-drama depicting a group of pilgrims uniting across diverse backgrounds on a life-changing expedition.",
                "duration": 150,
                "age_certificate": "U",
                "language": language_objs["ta"],
                "genres": [genre_objs["Drama"]],
                "director": "Gopinath",
                "trailer_url": "https://www.youtube.com/watch?v=8mrVn23Z5L4",
                "release_date": datetime.date(2026, 8, 14),
                "rating": 4.8,
                "poster": "https://images.unsplash.com/photo-1519817650390-64a93db51149?w=600&auto=format&fit=crop&q=80",
                "backdrop": "https://images.unsplash.com/photo-1506744038136-46273834b3fb?w=1200&auto=format&fit=crop&q=80",
            },

            # --- 2026 International / Worldwide Releases ---
            {
                "title": "Spider-Man: Brand New Day",
                "description": "The blockbuster summer 2026 chapter where Peter Parker faces high-tech Multiverse anomalies while protecting New York City.",
                "duration": 158,
                "age_certificate": "U/A",
                "language": language_objs["en"],
                "genres": [genre_objs["Action"], genre_objs["Sci-Fi"], genre_objs["Adventure"]],
                "director": "Destin Daniel Cretton",
                "trailer_url": "https://www.youtube.com/watch?v=cqGjhVJWtEg",
                "release_date": datetime.date(2026, 7, 24),
                "rating": 4.9,
                "poster": "https://images.unsplash.com/photo-1635805737707-575885ab0820?w=600&auto=format&fit=crop&q=80",
                "backdrop": "https://images.unsplash.com/photo-1607604276583-eef5d076aa5f?w=1200&auto=format&fit=crop&q=80",
            },
            {
                "title": "The Odyssey",
                "description": "A cinematic epic adaptation of Homer's legendary hero Odysseus navigating treacherous mythical seas to reach his home kingdom.",
                "duration": 175,
                "age_certificate": "U/A",
                "language": language_objs["en"],
                "genres": [genre_objs["Drama"], genre_objs["Adventure"]],
                "director": "Ralph Fiennes",
                "trailer_url": "https://www.youtube.com/watch?v=Way9Dexny3w",
                "release_date": datetime.date(2026, 7, 17),
                "rating": 4.8,
                "poster": "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?w=600&auto=format&fit=crop&q=80",
                "backdrop": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=1200&auto=format&fit=crop&q=80",
            },
            {
                "title": "The End of Oak Street",
                "description": "A psychological mystery thriller about a quiet suburban neighborhood uncovering dark secrets behind a sudden disappearance.",
                "duration": 142,
                "age_certificate": "A",
                "language": language_objs["en"],
                "genres": [genre_objs["Mystery"], genre_objs["Thriller"]],
                "director": "David Fincher",
                "trailer_url": "https://www.youtube.com/watch?v=uYPbbksJxIg",
                "release_date": datetime.date(2026, 6, 19),
                "rating": 4.7,
                "poster": "https://images.unsplash.com/photo-1509198397868-475647b2a1e5?w=600&auto=format&fit=crop&q=80",
                "backdrop": "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?w=1200&auto=format&fit=crop&q=80",
            },
            {
                "title": "Tony",
                "description": "A gritty mob crime drama depicting the rise and fall of a charismatic syndicate figure in 1970s New York.",
                "duration": 168,
                "age_certificate": "A",
                "language": language_objs["en"],
                "genres": [genre_objs["Drama"], genre_objs["Crime"]],
                "director": "Martin Scorsese",
                "trailer_url": "https://www.youtube.com/watch?v=EXeTwQWrcwY",
                "release_date": datetime.date(2026, 7, 10),
                "rating": 4.9,
                "poster": "https://images.unsplash.com/photo-1536440136628-849c177e76a1?w=600&auto=format&fit=crop&q=80",
                "backdrop": "https://images.unsplash.com/photo-1517604931442-7e0c8ed2963c?w=1200&auto=format&fit=crop&q=80",
            },
            {
                "title": "Insidious: Out of the Further",
                "description": "The terrifying August 2026 supernatural horror saga delving deeper into the dark realms beyond.",
                "duration": 138,
                "age_certificate": "A",
                "language": language_objs["en"],
                "genres": [genre_objs["Horror"], genre_objs["Thriller"]],
                "director": "James Wan",
                "trailer_url": "https://www.youtube.com/watch?v=KVnheXywIbU",
                "release_date": datetime.date(2026, 8, 21),
                "rating": 4.6,
                "poster": "https://images.unsplash.com/photo-1509198397868-475647b2a1e5?w=600&auto=format&fit=crop&q=80",
                "backdrop": "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?w=1200&auto=format&fit=crop&q=80",
            },

            # --- Catalog Favorites ---
            {
                "title": "Leo — Bloody Sweet",
                "description": "A mild-mannered cafe owner in Himachal Pradesh becomes a local hero through an act of violence, triggering chain events involving a ruthless drug cartel that claims he is their long-lost brother.",
                "duration": 164,
                "age_certificate": "A",
                "language": language_objs["ta"],
                "genres": [genre_objs["Action"], genre_objs["Thriller"], genre_objs["Crime"]],
                "director": "Lokesh Kanagaraj",
                "trailer_url": "https://www.youtube.com/watch?v=Po3jStA673E",
                "release_date": datetime.date(2023, 10, 19),
                "rating": 4.9,
                "poster": "https://images.unsplash.com/photo-1536440136628-849c177e76a1?w=600&auto=format&fit=crop&q=80",
                "backdrop": "https://images.unsplash.com/photo-1517604931442-7e0c8ed2963c?w=1200&auto=format&fit=crop&q=80",
            },
            {
                "title": "Jailer",
                "description": "A retired prison warden sets out on a relentless vigilante crusade to find his missing policeman son, unleashing his formidable underworld network.",
                "duration": 168,
                "age_certificate": "U/A",
                "language": language_objs["ta"],
                "genres": [genre_objs["Action"], genre_objs["Comedy"], genre_objs["Crime"]],
                "director": "Nelson Dilipkumar",
                "trailer_url": "https://www.youtube.com/watch?v=Y5BeWdODb7U",
                "release_date": datetime.date(2023, 8, 10),
                "rating": 4.8,
                "poster": "https://images.unsplash.com/photo-1579783902614-a3fb3927b675?w=600&auto=format&fit=crop&q=80",
                "backdrop": "https://images.unsplash.com/photo-1534447677768-be436bb09401?w=1200&auto=format&fit=crop&q=80",
            },
            {
                "title": "Vikram",
                "description": "A high-stakes special black-ops squad investigates a masked syndicate of serial killings, uncovering a deep-rooted narcotic conspiracy.",
                "duration": 175,
                "age_certificate": "U/A",
                "language": language_objs["ta"],
                "genres": [genre_objs["Action"], genre_objs["Thriller"]],
                "director": "Lokesh Kanagaraj",
                "trailer_url": "https://www.youtube.com/watch?v=OKBMCL-frPU",
                "release_date": datetime.date(2022, 6, 3),
                "rating": 4.9,
                "poster": "https://images.unsplash.com/photo-1509198397868-475647b2a1e5?w=600&auto=format&fit=crop&q=80",
                "backdrop": "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?w=1200&auto=format&fit=crop&q=80",
            },
            {
                "title": "The GOAT — Greatest of All Time",
                "description": "An elite counter-terrorism operative returns to action after decades, facing an unexpectedly familiar threat that endangers his family and homeland.",
                "duration": 178,
                "age_certificate": "U/A",
                "language": language_objs["ta"],
                "genres": [genre_objs["Action"], genre_objs["Sci-Fi"], genre_objs["Thriller"]],
                "director": "Venkat Prabhu",
                "trailer_url": "https://www.youtube.com/watch?v=jxCRlebiebw",
                "release_date": datetime.date(2024, 9, 5),
                "rating": 4.7,
                "poster": "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?w=600&auto=format&fit=crop&q=80",
                "backdrop": "https://images.unsplash.com/photo-1478760329108-5c3ed9d495a0?w=1200&auto=format&fit=crop&q=80",
            },
            {
                "title": "Amaran",
                "description": "The inspiring real-life journey of Major Mukund Varadarajan and his valor during anti-terrorist operations in Jammu and Kashmir.",
                "duration": 169,
                "age_certificate": "U/A",
                "language": language_objs["ta"],
                "genres": [genre_objs["Action"], genre_objs["Drama"]],
                "director": "Rajkumar Periasamy",
                "trailer_url": "https://www.youtube.com/watch?v=hylIXfZeB4c",
                "release_date": datetime.date(2024, 10, 31),
                "rating": 4.9,
                "poster": "https://images.unsplash.com/photo-1509062522246-3755977927d7?w=600&auto=format&fit=crop&q=80",
                "backdrop": "https://images.unsplash.com/photo-1506744038136-46273834b3fb?w=1200&auto=format&fit=crop&q=80",
            },
        ]

        created_movies = []
        for m_data in movies_dataset:
            # Query TMDB API dynamically if TMDB_API_KEY is present
            tmdb_images = self.fetch_tmdb_images(m_data["title"])
            poster_url = (tmdb_images and tmdb_images.get('poster')) or m_data.get('poster') or "https://images.unsplash.com/photo-1536440136628-849c177e76a1?w=600&auto=format&fit=crop&q=80"
            backdrop_url = (tmdb_images and tmdb_images.get('backdrop')) or m_data.get('backdrop') or "https://images.unsplash.com/photo-1517604931442-7e0c8ed2963c?w=1200&auto=format&fit=crop&q=80"

            movie, created = Movie.objects.get_or_create(
                title=m_data["title"],
                defaults={
                    "description": m_data["description"],
                    "duration": m_data["duration"],
                    "age_certificate": m_data["age_certificate"],
                    "language": m_data["language"],
                    "director": m_data["director"],
                    "trailer_url": m_data["trailer_url"],
                    "release_date": m_data["release_date"],
                    "average_rating": m_data["rating"],
                    "total_reviews": 24,
                    "is_active": True,
                }
            )
            if created:
                for g in m_data["genres"]:
                    movie.genres.add(g)
                for cast_member in cast_objs[:4]:
                    movie.cast.add(cast_member)

            # Ensure Primary Poster MovieImage exists
            MovieImage.objects.get_or_create(
                movie=movie,
                image_type='poster',
                is_primary=True,
                defaults={'image_url': poster_url, 'caption': f"{movie.title} Poster"}
            )
            # Ensure Backdrop MovieImage exists
            MovieImage.objects.get_or_create(
                movie=movie,
                image_type='backdrop',
                is_primary=False,
                defaults={'image_url': backdrop_url, 'caption': f"{movie.title} Backdrop"}
            )
            # Ensure at least 2 Gallery MovieImages exist
            MovieImage.objects.get_or_create(
                movie=movie,
                image_type='gallery',
                caption=f"{movie.title} Still 1",
                defaults={'image_url': poster_url}
            )
            MovieImage.objects.get_or_create(
                movie=movie,
                image_type='gallery',
                caption=f"{movie.title} Still 2",
                defaults={'image_url': backdrop_url}
            )

            created_movies.append(movie)

        self.stdout.write(self.style.SUCCESS(f"Seeded {len(created_movies)} movies with posters, backdrops & gallery stills."))

        # 5. Seed Theaters across Indian Cities (Demo Theater Data)
        theaters_dataset = [
            # Chennai
            ("Luxe Cinemas", "Royapettah", "Chennai", "Express Avenue Mall, Royapettah", 8, "IMAX 4K, Dolby Atmos, VIP Lounge, Recliners, Food Court, Parking"),
            ("Rohini Silver Screens", "Koyambedu", "Chennai", "123 Poonamallee High Rd, Koyambedu", 6, "Dolby Atmos, RGB Laser, Recliner Seats, Food Court"),
            ("AGS Cinemas Velachery", "Velachery", "Chennai", "1/139 Bypass Rd, Velachery", 5, "Dolby Atmos, 4K Projection, Food Court, Parking"),
            ("Sathyam Cinemas", "Royapettah", "Chennai", "8 Thiruvalluvar Salai, Royapettah", 6, "SPI RDX, Dolby Atmos, Landmark Popcorn"),
            ("Kamala Cinemas", "Vadapalani", "Chennai", "183 Arcot Rd, Vadapalani", 2, "4K Projection, Dolby Atmos, Parking"),
            ("Devi Cineplex", "Anna Salai", "Chennai", "48 Mount Road, Anna Salai", 4, "70mm Giant Screen, 4K Projection"),
            ("Mayajaal Multiplex", "ECR", "Chennai", "1/105 East Coast Road, Kanathur", 16, "16 Screens, Gaming Arcade, Bowling, Food Court"),
            ("Escape Cinemas", "Royapettah", "Chennai", "Express Avenue, 3rd Floor, Royapettah", 8, "Luxe Seating, Dolby Atmos, Food Lounge"),
            ("Vettri Theatres", "Chromepet", "Chennai", "51 GST Road, Chromepet", 2, "RGB Laser, Dolby Atmos, Recliners"),
            ("PVR INOX VR Mall", "Anna Nagar", "Chennai", "VR Chennai Mall, 100 Feet Rd", 10, "IMAX 4K, Dolby Atmos, Gold Class"),
            ("Cinepolis Grand Mall", "Velachery", "Chennai", "Velachery Main Rd", 5, "VIP Lounge, Dolby Atmos, 4K"),

            # Coimbatore
            ("KG Cinemas", "Race Course", "Coimbatore", "Bunny Complex, Race Course Rd", 4, "4K Dolby Atmos, Food Court, Parking"),
            ("SPI Brookefields", "RS Puram", "Coimbatore", "Brookefields Mall, Krishnaswamy Rd", 6, "SPI Sound, 4K RGB Laser, Recliners"),
            ("Fun Cinema", "Peelamedu", "Coimbatore", "Fun Republic Mall, Avinashi Rd", 5, "Dolby Atmos, Food Lounge, Gaming Zone"),
            ("Prozone Multiplex", "Saravanampatti", "Coimbatore", "Prozone Mall, Sathy Rd", 9, "IMAX, Dolby Atmos, Parking"),
            ("The Cinema", "Cross Cut Road", "Coimbatore", "Gandhipuram, Cross Cut Rd", 3, "Digital Projection, Air Conditioned"),

            # Madurai, Trichy, Salem, Tirunelveli
            ("Gopuram Cinemas", "KK Nagar", "Madurai", "80 Feet Rd, KK Nagar", 4, "Dolby Atmos, 4K Projection"),
            ("Vetri Cinemas", "Villapuram", "Madurai", "Aruppukottai Main Rd", 2, "Laser Projection, Sound System"),
            ("LA Cinemas", "Maris Theatre Complex", "Trichy", "Fort Station Rd, Trichy", 4, "Dolby Atmos, RGB Projection"),
            ("ARRS Multiplex", "Meyyanur", "Salem", "ARRS Tower, Meyyanur Main Rd", 5, "Dolby Atmos, 4K Laser"),
            ("Ram Muthuram Cinemas", "Palayamkottai", "Tirunelveli", "Tiruchendur Rd", 2, "Dolby Atmos, RGB Laser"),

            # Bengaluru
            ("PVR Forum Mall", "Koramangala", "Bengaluru", "Forum Mall, Hosur Rd", 11, "IMAX, 4DX, Gold Class, Dolby Atmos"),
            ("INOX Lido Mall", "MG Road", "Bengaluru", "1/2 Swami Vivekananda Rd", 4, "Insignia Lounge, Dolby Atmos"),
            ("Cinepolis Orion Mall", "Rajajinagar", "Bengaluru", "Dr Rajkumar Rd", 11, "VIP Recliners, Dolby Atmos, 4K"),

            # Hyderabad
            ("Prasads Multiplex", "NTR Gardens", "Hyderabad", "LIC Building Rd", 7, "Large Screen 4K, Dolby Atmos, Gaming Zone"),
            ("AMB Cinemas", "Gachibowli", "Hyderabad", "Sarath City Capital Mall", 7, "VIP Lounge, Dolby Atmos, Laser 4K"),
            ("PVR Next Galleria", "Panjagutta", "Hyderabad", "Metro Station Mall", 6, "4DX, Dolby Atmos, Food Court"),

            # Mumbai & Delhi & Kochi
            ("PVR Phoenix Palladium", "Lower Parel", "Mumbai", "High Street Phoenix", 9, "IMAX, Director's Cut, Luxe Dining"),
            ("INOX Megaplex Inorbit", "Malad", "Mumbai", "Inorbit Mall", 11, "MX4D, ScreenX, Insignia Lounge"),
            ("PVR Director's Cut", "Vasant Kunj", "Delhi", "Ambience Mall", 4, "7-Star Luxury Cinema, Gourmet Food"),
            ("PVR Lulu Mall", "Edappally", "Kochi", "Lulu Shopping Mall", 9, "IMAX 4K, Gold Class, Dolby Atmos"),
        ]

        created_theaters = []
        for name, loc, city, addr, screens, fac in theaters_dataset:
            th = Theater.objects.filter(name=name, city=city).first()
            if not th:
                th = Theater.objects.create(
                    name=name,
                    city=city,
                    location=loc,
                    address=addr,
                    total_screens=screens,
                    facilities=fac,
                    is_active=True
                )
            created_theaters.append(th)

        self.stdout.write(self.style.SUCCESS(f"Seeded {len(created_theaters)} theaters."))

        # 6. Seed Shows (August 15 to August 22, 2026)
        today = timezone.now().date()
        show_slots = [
            (datetime.time(9, 30), datetime.time(12, 15)),
            (datetime.time(13, 0), datetime.time(15, 45)),
            (datetime.time(16, 30), datetime.time(19, 15)),
            (datetime.time(20, 0), datetime.time(22, 45)),
        ]

        price_tiers = [180.00, 220.00, 250.00, 280.00, 300.00, 350.00]
        occupancy_presets = [
            (120, 18),  # 85% occupied - Filling Fast
            (120, 6),   # 95% occupied - Almost Full
            (120, 48),  # 60% occupied - Available
            (120, 22),  # 81% occupied - Filling Fast
            (120, 9),   # 92% occupied - Almost Full
        ]

        shows_created_count = 0
        num_movies = len(created_movies)

        for day_offset in range(0, 8):
            show_date = today + datetime.timedelta(days=day_offset)
            for t_idx, theater in enumerate(created_theaters):
                screens_to_seed = min(theater.total_screens, 4)
                for s_num in range(1, screens_to_seed + 1):
                    screen_name = f"Screen {s_num}"
                    for slot_idx, (st_time, end_time) in enumerate(show_slots):
                        # Determine movie for this theater, screen, date, and slot deterministically
                        m_offset = (t_idx * 3 + s_num * 2 + slot_idx + day_offset) % num_movies
                        movie = created_movies[m_offset]
                        ticket_price = price_tiers[(t_idx + slot_idx) % len(price_tiers)]
                        tot_s, avail_s = occupancy_presets[(t_idx + slot_idx) % len(occupancy_presets)]

                        show_obj = Show.objects.filter(
                            theater=theater,
                            screen=screen_name,
                            show_date=show_date,
                            start_time=st_time
                        ).first()

                        if not show_obj:
                            try:
                                Show.objects.create(
                                    movie=movie,
                                    theater=theater,
                                    screen=screen_name,
                                    show_date=show_date,
                                    start_time=st_time,
                                    end_time=end_time,
                                    ticket_price=ticket_price,
                                    total_seats=tot_s,
                                    available_seats=avail_s,
                                    is_active=True,
                                )
                                shows_created_count += 1
                            except Exception:
                                pass

        self.stdout.write(self.style.SUCCESS(f"Seeded {shows_created_count} active show schedules across multi-city theaters."))

        # 7. Seed Demo User, Bookings & Payments
        demo_user, _ = User.objects.get_or_create(
            username="cinephile_pro",
            defaults={"email": "cinephile@cineverse.com", "first_name": "Alex", "last_name": "Rider"}
        )
        demo_user.set_password("cineverse123")
        demo_user.save()

        sample_shows = Show.objects.filter(is_active=True)[:4]
        for s_idx, s_obj in enumerate(sample_shows):
            b_ref = f"CV-SEED00{s_idx + 1}"
            booking, b_created = Booking.objects.get_or_create(
                booking_reference=b_ref,
                defaults={
                    "user": demo_user,
                    "show": s_obj,
                    "selected_seats": f"A{s_idx+1}, A{s_idx+2}",
                    "number_of_seats": 2,
                    "total_amount": s_obj.ticket_price * 2,
                    "status": "CONFIRMED",
                    "payment_status": "PAID",
                    "watched": True if s_idx == 0 else False,
                }
            )
            if b_created:
                from decimal import Decimal
                Payment.objects.create(
                    booking=booking,
                    payment_method="UPI",
                    transaction_reference=f"TXN-SEED00{s_idx + 1}",
                    ticket_amount=booking.total_amount,
                    convenience_fee=Decimal('30.00'),
                    taxes=Decimal('54.00'),
                    total_amount=booking.total_amount + Decimal('30.00') + Decimal('54.00'),
                    status="SUCCESS"
                )
                if s_idx == 0:
                    Review.objects.get_or_create(
                        user=demo_user,
                        movie=s_obj.movie,
                        defaults={
                            "rating": 5,
                            "comment": "Absolutely spectacular cinema experience! Superb sound and picture quality.",
                            "verified_viewer": True,
                        }
                    )
                    s_obj.movie.update_rating_summary()

        self.stdout.write(self.style.SUCCESS("Successfully completed CineVerse comprehensive seed data initialization!"))
