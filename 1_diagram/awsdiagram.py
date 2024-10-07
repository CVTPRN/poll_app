from diagrams import Diagram, Cluster, Edge
from diagrams.aws.compute import EC2, Lambda
from diagrams.aws.database import RDS
from diagrams.aws.network import ELB, Route53
from diagrams.aws.storage import S3
from diagrams.aws.general import Client

# Diagram létrehozása
with Diagram("Enhanced Voting Application Architecture", show=False):

    # Kliensek - szavazók
    client = Client("Users")

    # Route53 - DNS
    dns = Route53("DNS")

    # Load Balancer (ELB)
    lb = ELB("Load Balancer")

    # S3 - tárhely fájloknak
    storage = S3("S3 Bucket")

    # Cluster az EC2 példányokhoz
    with Cluster("Voting Application Cluster"):
        # Három EC2 példány a szavazási alkalmazáshoz
        ec2_instances = [EC2("App EC2 1"),
                         EC2("App EC2 2"),
                         EC2("App EC2 3")]

    # AWS Lambda funkció a speciális feladatokhoz
    lambda_func = Lambda("Comment Service Lambda")

    # RDS adatbázis (pl. PostgreSQL vagy MySQL)
    db = RDS("RDS Database")

    # Kapcsolatok létrehozása
    client >> dns >> lb  # Kliensek a DNS-en keresztül az ELB-hez
    lb >> ec2_instances  # ELB kapcsolódik az EC2 példányokhoz
    ec2_instances >> db  # EC2 példányok kapcsolódnak az adatbázishoz
    lambda_func >> db  # A Lambda funkció kapcsolódik az adatbázishoz
    ec2_instances >> storage  # EC2 példányok hozzáférnek az S3-hoz
    lambda_func >> storage  # Lambda funkció hozzáfér az S3-hoz
