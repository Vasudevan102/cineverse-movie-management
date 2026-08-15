import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model
from movies.models import Movie, Genre, Language, CastMember
from booking.models import Theater, Show, Booking, Payment
from reviews.models import Review

User = get_user_model()

class Command(BaseCommand):
    help = "Seeds 30+ movies, 35+ theaters, shows, occupancy data, and reviews for CineVerse"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Starting CineVerse seed data generation..."))

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
            "Sci-Fi", "Adventure", "Animation", "Crime", "Fantasy", "Family"
        ]
        genre_objs = {}
        for g_name in genres_data:
            g_obj, _ = Genre.objects.get_or_create(name=g_name)
            genre_objs[g_name] = g_obj

        # 3. Seed Cast Members
        cast_data = [
            ("Vijay", "Thalapathy", "Renowned Indian actor known for high-octane action blockbusters."),
            ("Rajinikanth", "Superstar", "Iconic actor with a massive legendary fan base worldwide."),
            ("Kamal Haasan", "Ulaganayagan", "Master of Indian cinema acclaimed for versatility and craft."),
            ("Suriya", "Rolex / Hero", "Award-winning actor known for intense portrayals and cinema."),
            ("Ajith Kumar", "AK", "Massive stardom actor famous for action thrillers and racing."),
            ("Dhanush", "Karthik", "International actor celebrated for realistic acting."),
            ("Sivakarthikeyan", "SK", "Popular entertainer loved by family audiences across Tamil Nadu."),
            ("Trisha Krishnan", "Kunduvan", "Leading Indian actress with decades of top-tier success."),
            ("Nayanthara", "Lady Superstar", "Prominent leading actress across South Indian film industries."),
            ("Robert Downey Jr.", "Iron Man", "Acclaimed Hollywood actor iconic for global blockbuster roles."),
            ("Cillian Murphy", "J. Robert Oppenheimer", "Oscar-winning Irish actor famed for cerebral character roles."),
            ("Shah Rukh Khan", "Pathaan", "King of Bollywood with global appeal."),
            ("Prabhas", "Karna / Amarendra", "Pan-Indian superstar actor."),
            ("Allu Arjun", "Pushpa Raj", "Icon Star known for blockbuster mass action films."),
            ("Fahadh Faasil", "Ranga / Bhanwar", "Powerhouse actor famed for nuanced portrayals."),
            ("Rishab Shetty", "Shiva", "Director and actor of cultural blockbuster phenomenon."),
        ]
        cast_objs = []
        for name, char_name, bio in cast_data:
            member, _ = CastMember.objects.get_or_create(
                name=name,
                defaults={'character_name': char_name, 'biography': bio}
            )
            cast_objs.append(member)

        # 4. Seed 32+ Movies
        movies_dataset = [
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
                "rating": 4.6,
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
                "rating": 4.7,
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
                "rating": 4.5,
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
                "rating": 4.8,
            },
            {
                "title": "Ponniyin Selvan: Part 2",
                "description": "Arulmozhi Varman continues his journey to secure the Chola throne amidst political intrigue, betrayal, and civil war in ancient South India.",
                "duration": 164,
                "age_certificate": "U/A",
                "language": language_objs["ta"],
                "genres": [genre_objs["Action"], genre_objs["Drama"], genre_objs["Adventure"]],
                "director": "Mani Ratnam",
                "trailer_url": "https://www.youtube.com/watch?v=KsH1O2uIeUk",
                "release_date": datetime.date(2023, 4, 28),
                "rating": 4.6,
            },
            {
                "title": "Oppenheimer",
                "description": "The story of American scientist J. Robert Oppenheimer and his role in the development of the atomic bomb during World War II.",
                "duration": 180,
                "age_certificate": "A",
                "language": language_objs["en"],
                "genres": [genre_objs["Drama"], genre_objs["Thriller"]],
                "director": "Christopher Nolan",
                "trailer_url": "https://www.youtube.com/watch?v=uYPbbksJxIg",
                "release_date": datetime.date(2023, 7, 21),
                "rating": 4.9,
            },
            {
                "title": "Dune: Part Two",
                "description": "Paul Atreides unites with Chani and the Fremen while seeking revenge against the conspirators who destroyed his family.",
                "duration": 166,
                "age_certificate": "U/A",
                "language": language_objs["en"],
                "genres": [genre_objs["Sci-Fi"], genre_objs["Adventure"], genre_objs["Action"]],
                "director": "Denis Villeneuve",
                "trailer_url": "https://www.youtube.com/watch?v=Way9Dexny3w",
                "release_date": datetime.date(2024, 3, 1),
                "rating": 4.8,
            },
            {
                "title": "Jawan",
                "description": "A high-octane emotional action thriller about a man driven by a personal vendetta to rectify the wrongs in society while keeping a promise.",
                "duration": 169,
                "age_certificate": "U/A",
                "language": language_objs["hi"],
                "genres": [genre_objs["Action"], genre_objs["Thriller"], genre_objs["Drama"]],
                "director": "Atlee",
                "trailer_url": "https://www.youtube.com/watch?v=COv52Qyctws",
                "release_date": datetime.date(2023, 9, 7),
                "rating": 4.7,
            },
            {
                "title": "Kalki 2898 AD",
                "description": "A modern avatar of Lord Vishnu is believed to have descended to Earth to protect the world from evil forces in a dystopian post-apocalyptic future.",
                "duration": 180,
                "age_certificate": "U/A",
                "language": language_objs["te"],
                "genres": [genre_objs["Sci-Fi"], genre_objs["Action"], genre_objs["Fantasy"]],
                "director": "Nag Ashwin",
                "trailer_url": "https://www.youtube.com/watch?v=kQDd1AhGIHk",
                "release_date": datetime.date(2024, 6, 27),
                "rating": 4.6,
            },
            {
                "title": "Manjummel Boys",
                "description": "A group of friends from a small town in Kerala embark on a vacation trip to Kodaikanal, where an unexpected rescue mission tests their bond.",
                "duration": 135,
                "age_certificate": "U",
                "language": language_objs["ml"],
                "genres": [genre_objs["Drama"], genre_objs["Adventure"]],
                "director": "Chidambaram",
                "trailer_url": "https://www.youtube.com/watch?v=id848Ww1YLo",
                "release_date": datetime.date(2024, 2, 22),
                "rating": 4.9,
            },
            {
                "title": "Kantara",
                "description": "When greed fuels a conflict between villagers and evil forces, a loyal champion taps into sacred tribal rituals to protect his people.",
                "duration": 148,
                "age_certificate": "U/A",
                "language": language_objs["kn"],
                "genres": [genre_objs["Action"], genre_objs["Drama"], genre_objs["Fantasy"]],
                "director": "Rishab Shetty",
                "trailer_url": "https://www.youtube.com/watch?v=8mrVn23Z5L4",
                "release_date": datetime.date(2022, 9, 30),
                "rating": 4.8,
            },
            {
                "title": "Viduthalai Part 1",
                "description": "A rookie police constable gets caught in a moral dilemma while hunting down a rebel leader fought for workers rights in rural hills.",
                "duration": 150,
                "age_certificate": "A",
                "language": language_objs["ta"],
                "genres": [genre_objs["Crime"], genre_objs["Drama"], genre_objs["Thriller"]],
                "director": "Vetrimaaran",
                "trailer_url": "https://www.youtube.com/watch?v=34dM3y2sW_Q",
                "release_date": datetime.date(2023, 3, 31),
                "rating": 4.7,
            },
            {
                "title": "Interstellar",
                "description": "When Earth becomes uninhabitable, a team of ex-NASA astronauts travels through a wormhole near Saturn in search of a new home for mankind.",
                "duration": 169,
                "age_certificate": "U/A",
                "language": language_objs["en"],
                "genres": [genre_objs["Sci-Fi"], genre_objs["Drama"], genre_objs["Adventure"]],
                "director": "Christopher Nolan",
                "trailer_url": "https://www.youtube.com/watch?v=zSWdZVtXT7E",
                "release_date": datetime.date(2014, 11, 7),
                "rating": 5.0,
            },
            {
                "title": "Spider-Man: Across the Spider-Verse",
                "description": "Miles Morales catapults across the Multiverse, meeting a team of Spider-People charged with protecting its very existence.",
                "duration": 140,
                "age_certificate": "U",
                "language": language_objs["en"],
                "genres": [genre_objs["Animation"], genre_objs["Action"], genre_objs["Adventure"]],
                "director": "Joaquim Dos Santos",
                "trailer_url": "https://www.youtube.com/watch?v=cqGjhVJWtEg",
                "release_date": datetime.date(2023, 6, 2),
                "rating": 4.9,
            },
            {
                "title": "Animal",
                "description": "A fierce father-son bond takes an increasingly dark turn when a son embarks on an obsessive path of vengeance against his father's assailants.",
                "duration": 201,
                "age_certificate": "A",
                "language": language_objs["hi"],
                "genres": [genre_objs["Action"], genre_objs["Crime"], genre_objs["Drama"]],
                "director": "Sandeep Reddy Vanga",
                "trailer_url": "https://www.youtube.com/watch?v=DYDmfmpmbyc",
                "release_date": datetime.date(2023, 12, 1),
                "rating": 4.3,
            },
            {
                "title": "Pushpa 2: The Rule",
                "description": "Pushpa Raj expands his red sandalwood empire while clashing with ruthless law enforcement officers determined to bring him down.",
                "duration": 170,
                "age_certificate": "U/A",
                "language": language_objs["te"],
                "genres": [genre_objs["Action"], genre_objs["Crime"], genre_objs["Drama"]],
                "director": "Sukumar",
                "trailer_url": "https://www.youtube.com/watch?v=1kMKhg8p_D8",
                "release_date": datetime.date(2024, 12, 5),
                "rating": 4.6,
            },
            {
                "title": "Aavesham",
                "description": "Three college students in Bengaluru land in trouble with local seniors and seek help from an eccentric local gangster named Ranga.",
                "duration": 158,
                "age_certificate": "U/A",
                "language": language_objs["ml"],
                "genres": [genre_objs["Comedy"], genre_objs["Action"], genre_objs["Crime"]],
                "director": "Jithu Madhavan",
                "trailer_url": "https://www.youtube.com/watch?v=L0yEMF8P84E",
                "release_date": datetime.date(2024, 4, 11),
                "rating": 4.8,
            },
            {
                "title": "The Dark Knight",
                "description": "When the menace known as the Joker wreaks havoc and chaos on Gotham City, Batman must accept one of the greatest psychological tests.",
                "duration": 152,
                "age_certificate": "U/A",
                "language": language_objs["en"],
                "genres": [genre_objs["Action"], genre_objs["Crime"], genre_objs["Drama"]],
                "director": "Christopher Nolan",
                "trailer_url": "https://www.youtube.com/watch?v=EXeTwQWrcwY",
                "release_date": datetime.date(2008, 7, 18),
                "rating": 5.0,
            },
            {
                "title": "Thangalaan",
                "description": "A tribal leader in 19th-century Kolar Gold Fields fights against British colonial forces and ancient mythical spirits protecting hidden treasures.",
                "duration": 156,
                "age_certificate": "U/A",
                "language": language_objs["ta"],
                "genres": [genre_objs["Action"], genre_objs["Drama"], genre_objs["Fantasy"]],
                "director": "Pa. Ranjith",
                "trailer_url": "https://www.youtube.com/watch?v=b4wS9Wv0Yf4",
                "release_date": datetime.date(2024, 8, 15),
                "rating": 4.4,
            },
            {
                "title": "Kanguva",
                "description": "A warlord in prehistoric times and a modern bounty hunter in Goa find their fates entangled across centuries through a shared bloodline.",
                "duration": 154,
                "age_certificate": "U/A",
                "language": language_objs["ta"],
                "genres": [genre_objs["Action"], genre_objs["Fantasy"], genre_objs["Adventure"]],
                "director": "Siva",
                "trailer_url": "https://www.youtube.com/watch?v=Po3jStA673E",
                "release_date": datetime.date(2024, 11, 14),
                "rating": 4.2,
            },
            {
                "title": "Stree 2",
                "description": "The town of Chanderi is haunted once again by a terrifying headless spirit, prompting the gang to seek unexpected supernatural help.",
                "duration": 149,
                "age_certificate": "U/A",
                "language": language_objs["hi"],
                "genres": [genre_objs["Comedy"], genre_objs["Horror"], genre_objs["Fantasy"]],
                "director": "Amar Kaushik",
                "trailer_url": "https://www.youtube.com/watch?v=KVnheXywIbU",
                "release_date": datetime.date(2024, 8, 15),
                "rating": 4.7,
            },
            {
                "title": "Premalu",
                "description": "A lighthearted romantic comedy following Sachin as he navigates career aspirations and unrequited love in Hyderabad.",
                "duration": 156,
                "age_certificate": "U",
                "language": language_objs["ml"],
                "genres": [genre_objs["Romance"], genre_objs["Comedy"]],
                "director": "Girish A. D.",
                "trailer_url": "https://www.youtube.com/watch?v=r_r2Z6tU19g",
                "release_date": datetime.date(2024, 2, 9),
                "rating": 4.8,
            },
            {
                "title": "Devara: Part 1",
                "description": "An epic sea-bound action saga depicting a fearless coastal leader who wages war against smugglers threatening his village's honor.",
                "duration": 178,
                "age_certificate": "U/A",
                "language": language_objs["te"],
                "genres": [genre_objs["Action"], genre_objs["Drama"]],
                "director": "Koratala Siva",
                "trailer_url": "https://www.youtube.com/watch?v=34dM3y2sW_Q",
                "release_date": datetime.date(2024, 9, 27),
                "rating": 4.5,
            },
            {
                "title": "Bramayugam",
                "description": "A court singer escapes slavery in 17th century Malabar only to discover a mysterious, ancient mansion ruled by an enigmatic master.",
                "duration": 139,
                "age_certificate": "A",
                "language": language_objs["ml"],
                "genres": [genre_objs["Horror"], genre_objs["Thriller"], genre_objs["Drama"]],
                "director": "Rahul Sadasivan",
                "trailer_url": "https://www.youtube.com/watch?v=id848Ww1YLo",
                "release_date": datetime.date(2024, 2, 15),
                "rating": 4.9,
            },
            {
                "title": "Avatar: The Way of Water",
                "description": "Jake Sully lives with his newfound family formed on the planet of Pandora. Once a familiar threat returns, Jake must work with Neytiri to protect their home.",
                "duration": 192,
                "age_certificate": "U/A",
                "language": language_objs["en"],
                "genres": [genre_objs["Sci-Fi"], genre_objs["Action"], genre_objs["Adventure"]],
                "director": "James Cameron",
                "trailer_url": "https://www.youtube.com/watch?v=d9MyW72ELq0",
                "release_date": datetime.date(2022, 12, 16),
                "rating": 4.8,
            },
            {
                "title": "Maharaja",
                "description": "A quiet barber files a police report claiming his beloved household item 'Lakshmi' has been stolen, triggering a dark investigation.",
                "duration": 142,
                "age_certificate": "U/A",
                "language": language_objs["ta"],
                "genres": [genre_objs["Action"], genre_objs["Crime"], genre_objs["Drama"]],
                "director": "Nithilan Swaminathan",
                "trailer_url": "https://www.youtube.com/watch?v=hylIXfZeB4c",
                "release_date": datetime.date(2024, 6, 14),
                "rating": 4.9,
            },
            {
                "title": "Sita Ramam",
                "description": "An orphaned soldier's life changes when he receives a letter from a girl named Sita. He sets out to find her and love blooms amidst war.",
                "duration": 163,
                "age_certificate": "U",
                "language": language_objs["te"],
                "genres": [genre_objs["Romance"], genre_objs["Drama"]],
                "director": "Hanu Raghavapudi",
                "trailer_url": "https://www.youtube.com/watch?v=8mrVn23Z5L4",
                "release_date": datetime.date(2022, 8, 5),
                "rating": 4.9,
            },
            {
                "title": "KGF: Chapter 2",
                "description": "In the blood-soaked Kolar Gold Fields, Rocky's name strikes fear into his foes while government forces view him as a threat to law and order.",
                "duration": 168,
                "age_certificate": "U/A",
                "language": language_objs["kn"],
                "genres": [genre_objs["Action"], genre_objs["Crime"], genre_objs["Drama"]],
                "director": "Prashanth Neel",
                "trailer_url": "https://www.youtube.com/watch?v=JKa05nyUmuQ",
                "release_date": datetime.date(2022, 4, 14),
                "rating": 4.8,
            },
            {
                "title": "Lover",
                "description": "An intense emotional drama exploring a turbulent six-year relationship tested by insecurity, career ambitions, and personal choices.",
                "duration": 146,
                "age_certificate": "U/A",
                "language": language_objs["ta"],
                "genres": [genre_objs["Romance"], genre_objs["Drama"]],
                "director": "Prabhuram Vyas",
                "trailer_url": "https://www.youtube.com/watch?v=r_r2Z6tU19g",
                "release_date": datetime.date(2024, 2, 9),
                "rating": 4.4,
            },
            {
                "title": "Lucky Baskhar",
                "description": "A middle-class bank cashier in 1980s Bombay orchestrates a daring financial scheme to climb the socioeconomic ladder.",
                "duration": 150,
                "age_certificate": "U/A",
                "language": language_objs["te"],
                "genres": [genre_objs["Drama"], genre_objs["Crime"], genre_objs["Thriller"]],
                "director": "Venky Atluri",
                "trailer_url": "https://www.youtube.com/watch?v=34dM3y2sW_Q",
                "release_date": datetime.date(2024, 10, 31),
                "rating": 4.7,
            },
            {
                "title": "Singham Again",
                "description": "DCP Bajirao Singham leads a formidable cop universe task force on a high-stakes mission across border lines to rescue his wife.",
                "duration": 144,
                "age_certificate": "U/A",
                "language": language_objs["hi"],
                "genres": [genre_objs["Action"], genre_objs["Crime"]],
                "director": "Rohit Shetty",
                "trailer_url": "https://www.youtube.com/watch?v=COv52Qyctws",
                "release_date": datetime.date(2024, 11, 1),
                "rating": 4.1,
            },
        ]

        created_movies = []
        for m_data in movies_dataset:
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
                    "total_reviews": 18,
                    "is_active": True,
                }
            )
            if created:
                for g in m_data["genres"]:
                    movie.genres.add(g)
                for cast_member in cast_objs[:4]:
                    movie.cast.add(cast_member)
            created_movies.append(movie)

        self.stdout.write(self.style.SUCCESS(f"Seeded {len(created_movies)} movies."))

        # 5. Seed 35+ Theaters
        theaters_dataset = [
            # Chennai
            ("Rohini Silver Screens", "Koyambedu", "Chennai", "123 Poonamallee High Rd, Koyambedu", 6, "Dolby Atmos, RGB Laser, Recliner Seats, Food Court"),
            ("PVR INOX Anna Nagar", "Anna Nagar", "Chennai", "VR Chennai Mall, 100 Feet Rd, Anna Nagar", 10, "IMAX 4K, Dolby Atmos, Gold Class, Parking"),
            ("AGS Cinemas Velachery", "Velachery", "Chennai", "1/139 Bypass Rd, Velachery", 5, "Dolby Atmos, 4K Projection, Food Court"),
            ("Luxe Cinemas", "Royapettah", "Chennai", "Express Avenue Mall, Royapettah", 8, "IMAX, Dolby Atmos, VIP Lounge, Valet Parking"),
            ("Sathyam Cinemas", "Royapettah", "Chennai", "8 Thiruvalluvar Salai, Royapettah", 6, "SPI RDX, Dolby Atmos, Landmark Popcorn"),
            ("Kamala Cinemas", "Vadapalani", "Chennai", "183 Arcot Rd, Vadapalani", 2, "4K Projection, Dolby Atmos, Parking"),
            ("Escape Cinemas", "Royapettah", "Chennai", "Express Avenue, 3rd Floor, Royapettah", 8, "Luxe Seating, Dolby Atmos, Food Lounge"),
            ("Mayajaal Multiplex", "ECR", "Chennai", "1/105 East Coast Road, Kanathur", 16, "16 Screens, Gaming Arcade, Bowling, Food Court"),
            ("Devi Cineplex", "Anna Salai", "Chennai", "48 Mount Road, Anna Salai", 4, "70mm Giant Screen, 4K Projection"),
            ("Vettri Theatres", "Chromepet", "Chennai", "51 GST Road, Chromepet", 2, "RGB Laser, Dolby Atmos, Recliners"),

            # Coimbatore
            ("KG Cinemas", "Race Course", "Coimbatore", "Bunny Complex, Race Course Rd", 4, "4K Dolby Atmos, Food Court"),
            ("SPI Brookefields", "RS Puram", "Coimbatore", "Brookefields Mall, Krishnaswamy Rd", 6, "SPI Sound, 4K RGB Laser, Recliners"),
            ("Fun Cinema", "Peelamedu", "Coimbatore", "Fun Republic Mall, Avinashi Rd", 5, "Dolby Atmos, Food Lounge, Gaming Zone"),
            ("Prozone Multiplex", "Saravanampatti", "Coimbatore", "Prozone Mall, Sathy Rd", 9, "IMAX, Dolby Atmos, Parking"),
            ("The Cinema", "Cross Cut Road", "Coimbatore", "Gandhipuram, Cross Cut Rd", 3, "Digital Projection, Air Conditioned"),

            # Madurai
            ("Gopuram Cinemas", "KK Nagar", "Madurai", "80 Feet Rd, KK Nagar", 4, "Dolby Atmos, 4K Projection"),
            ("Vetri Cinemas", "Villapuram", "Madurai", "Aruppukottai Main Rd, Villapuram", 2, "Laser Projection, Sound System"),
            ("Midland Theatres", "Goripalayam", "Madurai", "Goripalayam Main Rd", 2, "Air Conditioned, Parking"),

            # Bengaluru
            ("PVR Forum Mall", "Koramangala", "Bengaluru", "Forum Mall, Hosur Rd, Koramangala", 11, "IMAX, 4DX, Gold Class, Dolby Atmos"),
            ("INOX Lido Mall", "MG Road", "Bengaluru", "1/2 Swami Vivekananda Rd", 4, "Insignia Lounge, Dolby Atmos"),
            ("Cinepolis Orion Mall", "Rajajinagar", "Bengaluru", "Dr Rajkumar Rd, Rajajinagar", 11, "VIP Recliners, Dolby Atmos, 4K"),

            # Hyderabad
            ("Prasads Multiplex", "NTR Gardens", "Hyderabad", "LIC Building Rd, NTR Gardens", 7, "Large Screen 4K, Dolby Atmos, Gaming Zone"),
            ("AMB Cinemas", "Gachibowli", "Hyderabad", "Sarath City Capital Mall, Gachibowli", 7, "VIP Lounge, Dolby Atmos, Laser 4K"),
            ("PVR Next Galleria", "Panjagutta", "Hyderabad", "Irrum Manzil Metro Station Mall", 6, "4DX, Dolby Atmos, Food Court"),

            # Mumbai
            ("PVR Phoenix Palladium", "Lower Parel", "Mumbai", "High Street Phoenix, Lower Parel", 9, "IMAX, Director's Cut, Luxe Dining"),
            ("INOX Megaplex Inorbit", "Malad", "Mumbai", "Inorbit Mall, Malad West", 11, "MX4D, ScreenX, Insignia Lounge"),

            # Delhi
            ("PVR Director's Cut", "Vasant Kunj", "Delhi", "Ambience Mall, Nelson Mandela Marg", 4, "7-Star Luxury Cinema, Gourmet Food"),
            ("Delite Cinema", "Daryaganj", "Delhi", "Asaf Ali Rd, Daryaganj", 2, "Heritage Cinema, 4K Projection"),

            # Pune & Kochi & Others
            ("PVR Icon Pavilion", "Senapati Bapat Rd", "Pune", "The Pavilion Mall, SB Road", 6, "4K Laser, Dolby Atmos, Recliners"),
            ("PVR Lulu Mall", "Edappally", "Kochi", "Lulu Shopping Mall, Edappally", 9, "IMAX 4K, Gold Class, Dolby Atmos"),
            ("ARRS Multiplex", "Meyyanur", "Salem", "ARRS Tower, Meyyanur Main Rd", 5, "Dolby Atmos, 4K Laser"),
            ("LA Cinemas", "Maris Theatre Complex", "Trichy", "Fort Station Rd, Trichy", 4, "Dolby Atmos, RGB Projection"),
            ("Ram Muthuram Cinemas", "Palayamkottai", "Tirunelveli", "Tiruchendur Rd, Palayamkottai", 2, "Dolby Atmos, RGB Laser"),
        ]

        created_theaters = []
        for name, loc, city, addr, screens, fac in theaters_dataset:
            th, _ = Theater.objects.get_or_create(
                name=name,
                city=city,
                defaults={
                    "location": loc,
                    "address": addr,
                    "total_screens": screens,
                    "facilities": fac,
                    "is_active": True,
                }
            )
            created_theaters.append(th)

        self.stdout.write(self.style.SUCCESS(f"Seeded {len(created_theaters)} theaters."))

        # 6. Seed 150+ Shows with Realistic Rupee Prices & Varied Occupancy
        today = timezone.now().date()
        show_times = [
            (datetime.time(10, 30), datetime.time(13, 15)),
            (datetime.time(14, 30), datetime.time(17, 15)),
            (datetime.time(18, 30), datetime.time(21, 15)),
            (datetime.time(22, 0), datetime.time(23, 59)),
        ]

        price_tiers = [180.00, 200.00, 220.00, 280.00, 350.00]
        occupancy_presets = [
            (120, 15),  # 87% occupied - Filling Fast
            (120, 8),   # 93% occupied - Almost Full
            (120, 45),  # 62% occupied - Available
            (120, 24),  # 80% occupied - Filling Fast
            (120, 6),   # 95% occupied - Almost Full
        ]

        shows_created_count = 0
        for day_offset in range(0, 4):
            show_date = today + datetime.timedelta(days=day_offset)
            for m_idx, movie in enumerate(created_movies):
                assigned_theaters = created_theaters[m_idx % 3::3]
                for t_idx, theater in enumerate(assigned_theaters):
                    st_time, end_time = show_times[(m_idx + t_idx) % len(show_times)]
                    screen_name = f"Screen {(t_idx % theater.total_screens) + 1}"
                    ticket_price = price_tiers[(m_idx + t_idx) % len(price_tiers)]
                    tot_s, avail_s = occupancy_presets[(m_idx + t_idx) % len(occupancy_presets)]

                    if not Show.objects.filter(theater=theater, screen=screen_name, show_date=show_date, start_time=st_time).exists():
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

        self.stdout.write(self.style.SUCCESS(f"Seeded {shows_created_count} active show schedules."))

        # 7. Seed Demo User, Bookings & Payments
        demo_user, _ = User.objects.get_or_create(
            username="cinephile_pro",
            defaults={"email": "cinephile@cineverse.com", "first_name": "Alex", "last_name": "Rider"}
        )
        demo_user.set_password("cineverse123")
        demo_user.save()

        sample_shows = Show.objects.filter(is_active=True)[:3]
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

        self.stdout.write(self.style.SUCCESS("Successfully completed CineVerse seed data initialization!"))
