from dataclasses import dataclass
from pathlib import Path
import subprocess
import json

from Compiler.compilerLib import Compiler
from Compiler.types import sint, sfix
from Compiler.GC.types import sbitvec, sbit
from Compiler.library import print_ln, do_while, for_range, accept_client_connection, listen_for_clients, if_, if_e, else_, crash
from Compiler.util import if_else
from Compiler.circuit import sha3_256



@dataclass(frozen=True)
class TLSNProof:
    # private to party
    followers: int
    # public
    proof_path: Path
    delta: str
    zero_encodings: list[str]
    hash: int
    nonce: int


FILE_DIR = Path(__file__).parent
TLSN_PROJECT_ROOT = FILE_DIR.parent / 'tlsn'
# ls tlsn/examples
EXAMPLE_DIR = TLSN_PROJECT_ROOT / 'tlsn' / 'examples' / 'simple'
CMD_GEN_TLSN_PROOF = "cargo run --release --example simple_prover"
CMD_VERIFY_TLSN_PROOF = "cargo run --release --example simple_verifier"


MPSPDZ_PROJECT_ROOT = FILE_DIR
MPSPDZ_CIRCUIT_DIR = MPSPDZ_PROJECT_ROOT / 'Programs' / 'Source'


MPC_PROTOCOL = 'semi'
LOCAL_RUN = MPSPDZ_PROJECT_ROOT / "Scripts" / f"{MPC_PROTOCOL}.sh"
CIRCUIT_NAME = 'auth_with_tlsn'

NUM_PARTIES = 3
PARTY_DATA_DIR = MPSPDZ_PROJECT_ROOT / "Player-Data"
PARTY_DATA_DIR.mkdir(parents=True, exist_ok=True)


# Only supports 1 byte for now
WORD_SIZE = 16
WORDS_PER_LABEL = 8

COMMITMENT_HASH_SIZE = 32
ASCII_BASE = 48


def prepare_player_data(proofs: list[TLSNProof]):
    assert len(proofs) == NUM_PARTIES
    for i, proof in enumerate(proofs):
        party_data_file = PARTY_DATA_DIR / f"Input-P{i}-0"
        with open(party_data_file, "w") as f_data:
            followers = proof.followers
            f_data.write(f"{followers}\n")


def generate_tlsn_proofs() -> list[TLSNProof]:
    # Run the tlsn proof generation command
    proofs = []
    for party_index in range(NUM_PARTIES):
        print(f"Generating TLSN proof for party {party_index}")
        proof_file = FILE_DIR / f"tlsn-proof-p{party_index}.json"
        try:
            res = subprocess.run(
                f"cd {EXAMPLE_DIR} && {CMD_GEN_TLSN_PROOF} {party_index} {proof_file}",
                shell=True, capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as e:
            print(f"Error occurred: {e}")
            print(f"stdout:\n{e.stdout}")
            print(f"stderr:\n{e.stderr}")
            exit(1)
        # Parse the output and get this line "Party {} has {} followers"
        followers_line = next((line for line in res.stdout.splitlines() if line.startswith(f"Party {party_index} has ")), None)
        if not followers_line:
            raise ValueError(f"Could not find followers line for party {party_index}")
        followers = int(followers_line.split()[3])
        with open(proof_file, "r") as f_proof:
            proof_data = json.load(f_proof)
            private_openings = proof_data["substrings"]["private_openings"]
            assert len(private_openings) == 1, f"Expected 1 private opening, got {len(private_openings)}"
            commitment_index, openings = list(private_openings.items())[0]
            commitment_info, commitment = openings
            data_commitment_hash = bytes(commitment["hash"]).hex()
            data_commitment_nonce = bytes(commitment["nonce"]).hex()

            encodings = proof_data["encodings"]
            all_labels = []
            for e in encodings:
                delta = e["U8"]["state"]["delta"]
                labels = e["U8"]["labels"]
                assert len(delta) == WORD_SIZE, f"Expected {WORD_SIZE} bytes in delta, got {len(delta)}"
                delta_hex = bytes(delta).hex()
                assert len(labels) == WORDS_PER_LABEL, f"Expected {WORDS_PER_LABEL} labels, got {len(labels)}"
                for l in labels:
                    assert len(l) == WORD_SIZE, f"Expected {WORD_SIZE} bytes in label, got {len(l)}"
                    label_hex = bytes(l).hex()
                    all_labels.append(label_hex)
            assert len(all_labels) == WORDS_PER_LABEL * len(encodings), f"Expected {WORDS_PER_LABEL * len(encodings)} labels, got {len(all_labels)}"
        proofs.append(
            TLSNProof(
                followers=followers,
                proof_path=proof_file,
                delta=delta_hex,
                zero_encodings=all_labels,
                hash=data_commitment_hash,
                nonce=data_commitment_nonce
            )
        )
    return proofs



def compile_run(computation):
    compiler = Compiler()
    compiler.register_function(CIRCUIT_NAME)(computation)
    compiler.compile_func()

    try:
        command = f"PLAYERS={NUM_PARTIES} {LOCAL_RUN} {CIRCUIT_NAME}"
        print(f"Running command: {command}")
        res = subprocess.run(command, shell=True, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error occurred: {e}")
        print(f"stdout:\n{e.stdout}")
        print(f"stderr:\n{e.stderr}")
        exit(1)
    # Parse the output
    # output: avg_followers = 15
    # Reg[8] = 0xed7ec2253e5b9f15a2157190d87d4fd7f4949ab219978f9915d12c03674dd161 #
    # Reg[4] = 0xec6b82369f30ad1d25022d87ac5cc825995dba1e140390392b0d948d30f672a6 #
    # Reg[0] = 0x28059a08d116926177e4dfd87e72da4cd44966b61acc3f21870156b868b81e6a #
    output_lines = res.stdout.split('\n')
    avg_followers = None
    commitments = []
    for line in output_lines:
        # Case for 'output: avg_followers = 15'
        if line.startswith('output: avg_followers = '):
            avg_followers = int(line.split('=')[1].strip())
        # Case for 'Reg[0] = 0x28059a08d116926177e4dfd87e72da4cd44966b61acc3f21870156b868b81e6a #'
        elif line.startswith('Reg['):
            # 0xed7ec2253e5b9f15a2157190d87d4fd7f4949ab219978f9915d12c03674dd161 #
            after_equal = line.split('=')[1].strip()
            # ed7ec2253e5b9f15a2157190d87d4fd7f4949ab219978f9915d12c03674dd161
            reg_value = after_equal.split(' ')[0][2:]
            commitments.append(reg_value)

    print(f"stdout: {res.stdout}")
    # Extract the variables
    if avg_followers is None:
        raise ValueError("Missing avg_followers in MP-SPDZ output")
    if len(commitments) != NUM_PARTIES:
        raise ValueError(f"Missing commitments for all parties, expected {NUM_PARTIES}, got {len(commitments)}")
    return avg_followers, commitments


def verify_tlsn_proofs(proofs: list[TLSNProof], commitments_mpspdz: list[int]):
    assert len(proofs) == NUM_PARTIES
    for party_index, proof in enumerate(proofs):
        # Verify TLSN proof for party
        try:
            subprocess.run(
                f"cd {EXAMPLE_DIR} && {CMD_VERIFY_TLSN_PROOF} {proof.proof_path}",
                shell=True, capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as e:
            print(f"Error occurred: {e}")
            print(f"stdout:\n{e.stdout}")
            print(f"stderr:\n{e.stderr}")
            exit(1)
        # Get the first (and only) data commitment from the TLSN proof
        commitment_tlsn = proof.hash
        commitment_mpspdz = commitments_mpspdz[party_index]
        print(f"party {party_index}: commitment_tlsn = {commitment_tlsn}")
        print(f"party {party_index}: commitment_mpspdz = {commitment_mpspdz}")
        assert commitment_tlsn == commitment_mpspdz, f"Commitment encoding does not match for party {party_index}"


def get_followers_digits(followers: int):
    # get how many digits are needed to represent the followers
    return len(str(followers))


def main():
    print("Generating TLSN proofs for parties...")
    # proofs = generate_tlsn_proofs()
    # print(f"Proofs: {proofs}")

    # prf for 1 byte
    # proofs = [
    #     TLSNProof(followers=3, proof_path=FILE_DIR / 'tlsn-proof-p0.json', delta='2501fa5c2b50281d97cc4e63bb1beaef', zero_encodings=['b51d9f6c1d7133a3c2d307b431c7f3ea', '2842eaaf492880247548f2cb189c2f5b', 'f1844ae7b20ad935605c87878b0ffb96', 'd19b84012adf53dedc896ebb36f7decd', 'e9629218d15b7d0887ffa78c4c70d237', 'd7ce38f06c1b134f30ee3dcd5c947d54', '7e666304dbc6c6a48d270c6d4c71f789', '62a1e68e06fd1d02adeb3646cfb47601'], hash='dc249d3704656445a729cc36e39a2f62900fd24f79d20d0dc6f30a5f22ef8f06', nonce='2a0ffcbec6f9338b582694ed46504445e59f3159ad6b7cb035325450ccb31213'),
    #     TLSNProof(followers=7, proof_path=FILE_DIR / 'tlsn-proof-p1.json', delta='373649df4ba763efb80393526cd8914a', zero_encodings=['4072e2f7e1c271086b4e73ddfd01f55a', '9de71f0bc983a30a4f4d48e21e8202a5', '5abfda4890938dc295bde881e309e8ca', 'c03b03d33cf9f21d110c85c4e76b957c', 'b38ce9704025ed2dede2a17d878a207e', 'ff676722a58d98742644268c05abe19d', '02ee533f359a03c45302b2e1cf529b9f', '27b057b471aa76641263e71c82526310'], hash='9b1d8da9d318e47f0350ff28a517e082083b3cd230dd846c87c85998612c50bf', nonce='d25f6e5bb66954b8765ee15ce9b76eee77567f1c5d9254aeeacf4ba013a58ff6'),
    #     TLSNProof(followers=8, proof_path=FILE_DIR / 'tlsn-proof-p2.json', delta='a933d0765b313d91d518bda095977f78', zero_encodings=['4b88931361b0b69fa573e18995f84042', '659d0fc74b3a8fe2baa71f5917c20c16', 'de0c378c7ae34171fff72a8bf5c93ad2', '554f1ed3f33d8c522988407d6d6f84d1', '71413cfa8f91380a0edc510a93e07fca', '26eb86d3c2fa2187be7087f17233ebbb', '3db5b599d6b8590693ffda5f4a2be9bb', '06462ccd3c5e11b7839053b4b9860409'], hash='5f8f1b8aaee66105cd5f29c65f85448e5e6e8f4a76a1c22dc619cffd09fd3666', nonce='451fa29db39b2ede357f10011b1d5957fa2ceca56ff6ac83b75c68f75340da99')
    # ]

    # prf for 2 bytes (Originally get at https://mhchia.github.io/followers-page/party_0.html and party_1, party_2 correspondingly)
    # proofs = [TLSNProof(followers=11, proof_path=FILE_DIR/'tlsn-proof-p0.json', delta='c3476750d275a29c1f7699ddaf3c0a88', zero_encodings=['0960d033f5eab1209fe10a345070e987', '299f355b01d63c298c4b221db76b0425', '85327e5c82518d1c3450be2be2d57a8a', '26bd5c6bb74bd3312fd23e986834004a', 'c664711bc8c4f959780d357d0245ee17', 'e5cd0785909dd0e1e7375ddcc4b92a84', 'f830e6346fc971f40e7a1d6345d24a7b', '674ea56eb3cbda9fb3a69961d53d6899', '8aa80e830c90cd2c7d874bd68ce451eb', 'bc2c46a16274d5265dcba57ce415a38b', '3c553826a9d6a136601577cccd566292', '008618565201755ace66f030814df457', '63c67a844ed0ecee552dd06817914fd9', '22d4e84c139974c836d539af3e860bf3', 'e7577931074ba0c94797b229f25c7e60', '112dab8c82a748f6490e559b5dabb166'], hash='90a13d8300e9c3e352587d660ae1d38266a33d6eb5141f1bbdd1c648eba0c431', nonce='8ce660f3dc546487556a21fe8e3a841f27376f0a15d20ead0a42fd45d8abb422'),
    #           TLSNProof(followers=17, proof_path=FILE_DIR/'tlsn-proof-p1.json', delta='cb91e0cba591eb0602659fa009bffb0b', zero_encodings=['c8685eb34348fd760a9dc15599cf8b08', '19a732b7a41ec943079b61bcdb5adfd7', 'b6a2419526a16acddcc4555affd990b6', 'd9af87415de8f0403b8d232652794dc9', 'a85648e5912639730000fcb811f4c093', 'b759a187ebec24eacd52231aba3c408e', '716670b631c6111ae605eae117dcce41', '1588b194ce95da212ddad335194953ea', '95aa7565d7b865fbed467aa1d4638c34', '5660cff0ff01f327d260f6512fa4ece9', '52fe1557b76b9b510a506f01ddb0b4bf', 'e9107eaa5520c0910336dddadd24e2f3', '5315141ef323c1969c090bca0cd92c02', 'ca8029f50a66190b0c7ad6ee52f19c0b', 'e7801f6f3c54af3cca1151f61ac2f872', '66af3d21e5a44384c1c97578ea1613e5'], hash='34fa666e34607061a1b671b72c7e325ada72e837cdd4b386a72a917f79a574e7', nonce='aad536a4af997dc516746ced071d96d833e71260ffdb7d9b401aecdfb6d56750'),
    #           TLSNProof(followers=14, proof_path=FILE_DIR/'tlsn-proof-p2.json', delta='1771aea601cec2d8d8a2f1e6d912b21e', zero_encodings=['9db477a726956c417bb3e5108887d413', 'f1e0d7817ce6266c179b382de942ea68', 'fb1d0d9de4ae98afbca045e13d8dce78', 'bb27d6fe7faa30e7aca8b73fbdfea64c', 'c86a95976ef211d8e14f052ade111708', 'e52928fdea52a56e5138e62f580f5f8e', 'a7014a5930f4a167ace1c160d04398d1', '808ebe895bca34c87512e9f363c03f31', '8969a9052c7a578a846226dff9d0b831', 'b59c9636e44ef865db021bd1c25c894c', '9a4fc1e9458669fc133a3392dbd25545', '61a566193fdaef19667a69c51700dc98', '1dbf97a16a01dda014b895b2de7892f5', '9991f17599f51cd6251a2ef95f3082c9', '18c3b4783d9e5567ab6621c9b5b7b992', '48a6a3099b524745f51e1712d15508ee'], hash='80a902e355be6ea13fd659881fca77f56251a9a7754177239fd98a182744129a', nonce='9daeb705d00d4b3558361b334a40ca842b224fa694dc51f4e0b2f40dc7116343')]

    # prf for 3 bytes (Originally get at https://jernkunpittaya.github.io/followers-page/party_0.html and party_1, party_2 correspondingly)
    # proofs= [TLSNProof(followers=111, proof_path=FILE_DIR/'tlsn-proof-p0.json', delta='3ff8c49ac2d4f650db26e2b78a92eae5', zero_encodings=['0eb1bddc009cb670a03bf97572d2da65', 'a970215d4aa930676cfe51ef55ef8a27', '2c373503f595acdf43c3f375cbaf729a', 'bfe05d7b92de4767ca2d892c225ac037', 'ce75d41306824831e51d109642c41d3f', '96044d691d52a5b9eda231eb42408bc4', '99671f883beaa9443b164035d8c1aadd', '7a59495778a5636a969f546f437110c4', '183e388a6bd233e59a3531dd20b60cb5', '7b98a468ad9bc662d4a34707d36356f0', 'c80e4f3ad7ca898d11c1dee4b47f187e', '7f46e86a4ee0dc4f7e9534d34c3e6b48', '59c70ded1926058f0084577aa77f2df8', '22da66e29a7ae21cd586a852ec3c3b37', '22a11b19547dc46e09097589373340e0', 'fd9325744578ed96fa89c6f43f705ef3', '7637b14cc5898942b1144adadc54ae81', 'cc01302acb2dcc835a8254f5414a581a', '73f29faf9c86c958d3093c381395a48c', '5e2ab68ca79794b1abb93197bb584dc1', 'a3be78e8afa8fa8feb8d37a7dc416517', '3d3882303ac2cdc710e024c98724499b', 'a58c4ae4f6c506a7fff81439ac7e0c23', '7005010e4e4ac79f3712975e918af00b'], hash='e5bee8b6c2b7578c5c8e4a9a396b956afbb02336e84f577f66f570e496040f24', nonce='fb3c98d63dbb8f2be5d2257d6e29ce4f9d3fadd30176c2de75d79201ce13e5d9'),
    #          TLSNProof(followers=172, proof_path=FILE_DIR/'tlsn-proof-p1.json', delta='9b871524b16d3114c8af47db944e4272', zero_encodings=['87d2eb7e4114e565805f6ad2a31eedc3', '1e537af81e454dfe47d86a67b690b4fa', '95003e4d1911f19eff12107c83e827aa', '6b0632eed4b788b14d62432094482b10', '8f326a494e850d24fa33a4491a713168', '08dcb34eb7b1ecc0117fa31b58dd08de', 'd708dc5c8ec280ba377a47aad79bf2bc', '518729da7f10dcf59f9ac5b03226f673', 'e405a3c975751afbc2845c8e0fcd22f4', '89caac62e8bf2d29ad7bf973322ae0b3', 'f65e60379fc1008f84828249edaf04b5', 'c4546c76abbbbaa43c06159ac9698122', '068d660779a7b7fe10eae38cd6263f3f', '324a8fe0b7c9ee90ba4805063af17e4f', '5c985e75eded78a7a967c4f2feb027ee', '87f8c24bfd03f3783869f2a772dabbd7', 'd98e4de720e90499cc45c194e0a1429c', '69aec002f1a7cee41b82c60bbfa667a1', '24ff5dc5608b67ddbec1006ecefb8f30', 'abacee681e5fbec9b847a8c7bfd3e1f9', 'db16c9cad5eb15a6ec0a006cf2035cfc', 'a6d243559462eca5cbac567fdde346c5', '894db39662f10cb2130d997e27f101eb', 'cc5606d30f616edfd252dd3acabb9329'], hash='f893cb8cebc81e48ccb78873f40b3676f36fac4762f43c6cc66e4b7b1ee73c68', nonce='b757ea5fd3a9577aa7393736fd1af5c51e75821009b161ad31f1d9cb91a86180'),
    #          TLSNProof(followers=140, proof_path=FILE_DIR/'tlsn-proof-p2.json', delta='2bdbb23d17e9398c3a3551018c263d42', zero_encodings=['c4890e80238c8023369c1a506c37c41c', '7bdd3429de3d69f88d92960b98fcc52f', 'c52217bdd5e6b8f0df9e964157fe8972', 'd1c911a24cdac9a08d184e956a710def', 'e1cfc2d4dff0a72a8b712254cb2f96cc', 'd8f76f113cd80550bd8d1901a0251812', '6630dce65242e958685f025015946049', '9e5ff3a93b040858ab8cc5989e6db533', '803382f601f470e0742954918aa8e461', '646990e4b05835395c5e2821a3719230', 'f34d0d214e827a7e979bdaa8fc33eefc', '2a3ed2df97f1a6fee26ae4c2bfe6d896', 'd9ec5c26c03761357b640aa8dd353381', '023d9722e434de6dc1335465f940fbd4', '6bda26d44b4c30de689b1e5e88db8ffa', '795b37ae543f4545e0da99563bf3edc4', 'f12d62c79c10694cd5fc26fa01ca2185', 'd8aaec9e2fbf022f4a2fabb9e403e93d', '1ff41d83240cecd3365be966a3c578aa', '09f8ea09ded95efff943fc1f56c53043', '9f39847e04204006d38e0a44cd39a4cb', 'a1b4de355897e9cca4c1ae8e7f3d9870', '4f125d54d7f51257b36435db8f2c3b76', '0b7c5868109092cf1b76417f98cb20ca'], hash='2e9e7c2e980b12582881a6d2bebe9fb2d0c96c80e2e76535bda2b82d9e088d9b', nonce='735d9f41b8928ede53c2c2eeaa88365ad3ce3a2370362366ac43eba2d0f259b7')]

    # prf for different number of digits
    proofs= [
        TLSNProof(followers=3, proof_path=FILE_DIR / 'tlsn-proof-p0.json', delta='2501fa5c2b50281d97cc4e63bb1beaef', zero_encodings=['b51d9f6c1d7133a3c2d307b431c7f3ea', '2842eaaf492880247548f2cb189c2f5b', 'f1844ae7b20ad935605c87878b0ffb96', 'd19b84012adf53dedc896ebb36f7decd', 'e9629218d15b7d0887ffa78c4c70d237', 'd7ce38f06c1b134f30ee3dcd5c947d54', '7e666304dbc6c6a48d270c6d4c71f789', '62a1e68e06fd1d02adeb3646cfb47601'], hash='dc249d3704656445a729cc36e39a2f62900fd24f79d20d0dc6f30a5f22ef8f06', nonce='2a0ffcbec6f9338b582694ed46504445e59f3159ad6b7cb035325450ccb31213'),
        TLSNProof(followers=14, proof_path=FILE_DIR/'tlsn-proof-p2.json', delta='1771aea601cec2d8d8a2f1e6d912b21e', zero_encodings=['9db477a726956c417bb3e5108887d413', 'f1e0d7817ce6266c179b382de942ea68', 'fb1d0d9de4ae98afbca045e13d8dce78', 'bb27d6fe7faa30e7aca8b73fbdfea64c', 'c86a95976ef211d8e14f052ade111708', 'e52928fdea52a56e5138e62f580f5f8e', 'a7014a5930f4a167ace1c160d04398d1', '808ebe895bca34c87512e9f363c03f31', '8969a9052c7a578a846226dff9d0b831', 'b59c9636e44ef865db021bd1c25c894c', '9a4fc1e9458669fc133a3392dbd25545', '61a566193fdaef19667a69c51700dc98', '1dbf97a16a01dda014b895b2de7892f5', '9991f17599f51cd6251a2ef95f3082c9', '18c3b4783d9e5567ab6621c9b5b7b992', '48a6a3099b524745f51e1712d15508ee'], hash='80a902e355be6ea13fd659881fca77f56251a9a7754177239fd98a182744129a', nonce='9daeb705d00d4b3558361b334a40ca842b224fa694dc51f4e0b2f40dc7116343'),
        TLSNProof(followers=172, proof_path=FILE_DIR/'tlsn-proof-p1.json', delta='9b871524b16d3114c8af47db944e4272', zero_encodings=['87d2eb7e4114e565805f6ad2a31eedc3', '1e537af81e454dfe47d86a67b690b4fa', '95003e4d1911f19eff12107c83e827aa', '6b0632eed4b788b14d62432094482b10', '8f326a494e850d24fa33a4491a713168', '08dcb34eb7b1ecc0117fa31b58dd08de', 'd708dc5c8ec280ba377a47aad79bf2bc', '518729da7f10dcf59f9ac5b03226f673', 'e405a3c975751afbc2845c8e0fcd22f4', '89caac62e8bf2d29ad7bf973322ae0b3', 'f65e60379fc1008f84828249edaf04b5', 'c4546c76abbbbaa43c06159ac9698122', '068d660779a7b7fe10eae38cd6263f3f', '324a8fe0b7c9ee90ba4805063af17e4f', '5c985e75eded78a7a967c4f2feb027ee', '87f8c24bfd03f3783869f2a772dabbd7', 'd98e4de720e90499cc45c194e0a1429c', '69aec002f1a7cee41b82c60bbfa667a1', '24ff5dc5608b67ddbec1006ecefb8f30', 'abacee681e5fbec9b847a8c7bfd3e1f9', 'db16c9cad5eb15a6ec0a006cf2035cfc', 'a6d243559462eca5cbac567fdde346c5', '894db39662f10cb2130d997e27f101eb', 'cc5606d30f616edfd252dd3acabb9329'], hash='f893cb8cebc81e48ccb78873f40b3676f36fac4762f43c6cc66e4b7b1ee73c68', nonce='b757ea5fd3a9577aa7393736fd1af5c51e75821009b161ad31f1d9cb91a86180'),
    ]

    prepare_player_data(proofs)

    # MP-SPDZ circuit
    def computation():
        sfix.round_nearest = True
        def calculate_data_commitment(num_bytes_followers: int, followers: sint, delta: sbitvec, encoding: list[sbitvec], nonce: sbitvec):
            # `followers` is "Data" and `encoding` is the "Full Encoding"
            # Active coding is calculated from `followers` and `encoding`.
            # Ref:
            #   - docs: https://docs.tlsnotary.org/mpc/commitments.html#commitments
            #   - code: https://github.com/tlsnotary/tlsn/blob/e14d0cf563e866cde18d8cf7a79cfbe66d220acd/crates/core/src/commitment/blake3.rs#L76-L80
            followers_bits_list = []
            number = followers
            for i in range(num_bytes_followers):
                divisor = sint(10**(num_bytes_followers-1-i))
                # curr_digit = current digit tracing from MSB to LSB
                # Since int_div() requires bit of inputs, bit of inputs <= log_2(10**num_bytes_followers) < 4* num_bytes_followers
                curr_digit = number.int_div(divisor, 4*num_bytes_followers)
                followers_bits_list += [sbit(ele) for ele in sbitvec(curr_digit+ASCII_BASE, 8).v]
                number = number.int_mod(divisor, 4*num_bytes_followers)

            active_encoding:list[sbitvec] = []
            for i in range(len(encoding)):
                filtered_delta = []
                for j in range(len(delta)):
                    filtered_delta.append(followers_bits_list[i].if_else(delta[j], sbit(0)))
                filtered_delta = sbitvec.from_vec(filtered_delta)
                active_encoding.append(encoding[i].bit_xor(filtered_delta))


            concat = nonce.bit_decompose() + sbitvec(sint(num_bytes_followers), 8).bit_decompose()
            for i in range(len(encoding)):
                if i%8 ==0:
                    concat = concat + sbitvec(sint(1), 8).bit_decompose()
                concat = concat+active_encoding[i].bit_decompose()
            return sha3_256(sbitvec.compose(concat))

        # Private inputs
        followers_0 = sint.get_input_from(0)
        followers_1 = sint.get_input_from(1)
        followers_2 = sint.get_input_from(2)
        num_bytes_followers = [get_followers_digits(proof.followers) for proof in proofs]

        # Public inputs
        nonce_0 = sbitvec.from_hex(proofs[0].nonce)
        nonce_1 = sbitvec.from_hex(proofs[1].nonce)
        nonce_2 = sbitvec.from_hex(proofs[2].nonce)
        delta_0 = sbitvec.from_hex(proofs[0].delta)
        delta_1 = sbitvec.from_hex(proofs[1].delta)
        delta_2 = sbitvec.from_hex(proofs[2].delta)
        zero_encodings_0 = [sbitvec.from_hex(e) for e in proofs[0].zero_encodings]
        zero_encodings_1 = [sbitvec.from_hex(e) for e in proofs[1].zero_encodings]
        zero_encodings_2 = [sbitvec.from_hex(e) for e in proofs[2].zero_encodings]

        # Calculation
        avg_followers = (followers_0 + followers_1 + followers_2) / 3
        commitment_0 = calculate_data_commitment(num_bytes_followers[0], followers_0, delta_0, zero_encodings_0, nonce_0)
        commitment_1 = calculate_data_commitment(num_bytes_followers[1], followers_1, delta_1, zero_encodings_1, nonce_1)
        commitment_2 = calculate_data_commitment(num_bytes_followers[2], followers_2, delta_2, zero_encodings_2, nonce_2)

        # Outputs
        print_ln("output: avg_followers = %s", avg_followers.reveal())
        commitment_0.reveal_print_hex()
        commitment_1.reveal_print_hex()
        commitment_2.reveal_print_hex()

    print("Running MP-SPDZ circuit...")
    avg_followers, commitments_mpsdz = compile_run(computation)
    print("Verifying TLSN proofs...")
    verify_tlsn_proofs(proofs, commitments_mpsdz)
    print("\n\n\nTLSN proofs verified successfully and matched with MP-SPDZ output")
    print(f"Average followers: {avg_followers}")


if __name__ == "__main__":
    main()