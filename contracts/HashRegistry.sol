// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

/**
 * @title HashRegistry
 * @notice FaceChain — stores SHA-256 fingerprints of discovered social media posts.
 *         Each hash is registered once and can be verified by anyone on-chain.
 * @dev Deployed on Ethereum Sepolia Testnet
 */
contract HashRegistry {

    struct Record {
        address uploader;
        uint256 timestamp;
        string  metadata;   // post URL or label (max 200 chars recommended)
    }

    mapping(bytes32 => Record) private records;

    event HashRegistered(
        bytes32 indexed dataHash,
        address indexed uploader,
        uint256 timestamp,
        string  metadata
    );

    /**
     * @notice Register a SHA-256 hash on-chain. Reverts if already registered.
     * @param dataHash  32-byte SHA-256 hash of the discovered post data
     * @param metadata  Human-readable label (e.g. post URL)
     */
    function registerHash(bytes32 dataHash, string calldata metadata) external {
        require(records[dataHash].timestamp == 0, "HashRegistry: already registered");
        records[dataHash] = Record({
            uploader:  msg.sender,
            timestamp: block.timestamp,
            metadata:  metadata
        });
        emit HashRegistered(dataHash, msg.sender, block.timestamp, metadata);
    }

    /**
     * @notice Verify whether a hash has been registered.
     * @param dataHash  32-byte SHA-256 hash to look up
     * @return exists    true if the hash is on record
     * @return uploader  address that registered it
     * @return timestamp Unix timestamp of registration
     * @return metadata  label stored alongside the hash
     */
    function verifyHash(bytes32 dataHash)
        external
        view
        returns (
            bool    exists,
            address uploader,
            uint256 timestamp,
            string  memory metadata
        )
    {
        Record memory r = records[dataHash];
        if (r.timestamp == 0) {
            return (false, address(0), 0, "");
        }
        return (true, r.uploader, r.timestamp, r.metadata);
    }
}
